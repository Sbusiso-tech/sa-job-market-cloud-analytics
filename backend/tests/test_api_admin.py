import json

import pytest
from botocore.exceptions import ClientError

from conftest import ADMIN, USER_A, api_event, body_of
from handlers import api_admin
from sajobs.repository import Repository


def call(route, claims=ADMIN):
    return api_admin.handler(api_event(route, claims=claims))


@pytest.mark.parametrize("route", ["POST /api/admin/runs", "GET /api/admin/runs"])
@pytest.mark.parametrize(
    "claims, status",
    [
        (USER_A, 403),
        ({**USER_A, "cognito:groups": "[users]"}, 403),
        ({**USER_A, "cognito:groups": ["admin"]}, 403),
        (None, 401),
    ],
)
def test_non_admins_rejected(cloud, route, claims, status):
    response = call(route, claims)
    assert response["statusCode"] == status
    assert body_of(response)["error"]["code"] == ("forbidden" if status == 403 else "unauthorized")


@pytest.mark.parametrize("groups", ["[admins]", ["admins"], "[users admins]"])
def test_group_claim_formats_accepted(cloud, groups):
    assert call("GET /api/admin/runs", {**ADMIN, "cognito:groups": groups})["statusCode"] == 200


def test_start_and_list_runs(cloud):
    response = call("POST /api/admin/runs")
    assert response["statusCode"] == 202
    started = body_of(response)
    assert started["execution_id"].startswith("manual-") and started["started_at"].endswith("Z")
    execution = cloud.sfn.list_executions(stateMachineArn=cloud.state_machine)["executions"][0]
    assert execution["name"] == started["execution_id"]
    described = cloud.sfn.describe_execution(executionArn=execution["executionArn"])
    assert json.loads(described["input"]) == {"use_sample": False}

    Repository(cloud.table).start_run(started["execution_id"], fetched=40, source="adzuna",
                                      started_at=started["started_at"])
    Repository(cloud.table).add_run_counts(started["execution_id"], new_jobs=7)
    cloud.sqs.send_message(QueueUrl=cloud.dlq_url, MessageBody="poison")

    listing = body_of(call("GET /api/admin/runs"))
    assert listing["dlq_depth"] == 1
    run = listing["runs"][0]
    assert run["execution_id"] == started["execution_id"]
    assert run["status"] in {"RUNNING", "SUCCEEDED"}
    assert (run["fetched"], run["new_jobs"], run["failed"]) == (40, 7, 0)
    assert set(run) == {"execution_id", "status", "started_at", "stopped_at", "fetched", "new_jobs", "failed"}


def test_runs_without_counts_are_null(cloud, monkeypatch):
    from datetime import UTC, datetime

    class FakeSfn:
        def list_executions(self, **kwargs):
            return {"executions": [{"name": "x", "status": "PENDING_REDRIVE", "startDate": datetime(2026, 1, 1,
                                                                                                    tzinfo=UTC)}]}

    real = api_admin.aws.client

    monkeypatch.setattr(api_admin.aws, "client", lambda name: FakeSfn() if name == "stepfunctions" else real(name))
    run = body_of(call("GET /api/admin/runs"))["runs"][0]
    assert run == {"execution_id": "x", "status": "FAILED", "started_at": "2026-01-01T00:00:00Z",
                   "stopped_at": None, "fetched": None, "new_jobs": None, "failed": None}


def test_duplicate_execution_name_is_409(cloud, monkeypatch):
    class Dup:
        def start_execution(self, **kwargs):
            raise ClientError({"Error": {"Code": "ExecutionAlreadyExists", "Message": "dup"}}, "StartExecution")

    monkeypatch.setattr(api_admin.aws, "client", lambda name: Dup())
    response = call("POST /api/admin/runs")
    assert response["statusCode"] == 409 and body_of(response)["error"]["code"] == "limit_reached"


def test_other_sfn_errors_are_500(cloud, monkeypatch):
    class Broken:
        def start_execution(self, **kwargs):
            raise ClientError({"Error": {"Code": "AccessDenied", "Message": "no"}}, "StartExecution")

    monkeypatch.setattr(api_admin.aws, "client", lambda name: Broken())
    response = call("POST /api/admin/runs")
    assert response["statusCode"] == 500 and body_of(response)["error"]["code"] == "internal"
