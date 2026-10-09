"""Admin routes (``/api/admin/*``): callers must be in the Cognito ``admins`` group."""
from __future__ import annotations

import json
import os
from typing import Any

from botocore.exceptions import ClientError

from sajobs import aws
from sajobs.http import ApiError, dispatch, get_claims, get_groups, json_response, require_sub
from sajobs.models import format_datetime, utc_now
from sajobs.repository import Repository

ADMIN_GROUP = "admins"
MAX_RUNS = 20
STATUSES = {"RUNNING", "SUCCEEDED", "FAILED", "TIMED_OUT", "ABORTED"}


def _require_admin(event: dict[str, Any]) -> None:
    claims = get_claims(event)
    require_sub(claims)
    if ADMIN_GROUP not in get_groups(claims):
        raise ApiError(403, "Admin access required")


def start_run(event):
    _require_admin(event)
    now = utc_now()
    name = f"manual-{now.strftime('%Y%m%dT%H%M%SZ')}"
    try:
        aws.client("stepfunctions").start_execution(
            stateMachineArn=os.environ["STATE_MACHINE_ARN"], name=name, input=json.dumps({"use_sample": False})
        )
    except ClientError as exc:
        if exc.response["Error"]["Code"] == "ExecutionAlreadyExists":
            raise ApiError(409, "A run was started a moment ago", "limit_reached") from exc
        raise
    return json_response(202, {"execution_id": name, "started_at": format_datetime(now)})


def _iso(value: Any) -> str | None:
    return format_datetime(value) if value else None


def list_runs(event):
    _require_admin(event)
    executions = aws.client("stepfunctions").list_executions(
        stateMachineArn=os.environ["STATE_MACHINE_ARN"], maxResults=MAX_RUNS
    )["executions"]
    repo = Repository(aws.table())
    runs = []
    for execution in sorted(executions, key=lambda e: e["startDate"], reverse=True)[:MAX_RUNS]:
        record = repo.get_run(execution["name"]) or {}
        status = execution.get("status")
        runs.append(
            {
                "execution_id": execution["name"],
                "status": status if status in STATUSES else "FAILED",
                "started_at": _iso(execution.get("startDate")),
                "stopped_at": _iso(execution.get("stopDate")),
                "fetched": record.get("fetched"),
                "new_jobs": record.get("new_jobs"),
                "failed": record.get("failed"),
            }
        )
    attributes = aws.client("sqs").get_queue_attributes(
        QueueUrl=os.environ["DLQ_URL"], AttributeNames=["ApproximateNumberOfMessages"]
    )["Attributes"]
    return json_response(200, {"dlq_depth": int(attributes.get("ApproximateNumberOfMessages", 0)), "runs": runs})


ROUTES = {
    "POST /api/admin/runs": start_run,
    "GET /api/admin/runs": list_runs,
}


def handler(event: dict[str, Any], context: Any = None) -> dict[str, Any]:
    return dispatch(event, ROUTES)
