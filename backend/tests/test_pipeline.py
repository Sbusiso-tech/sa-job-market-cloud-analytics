import gzip
import json
from datetime import UTC, datetime, timedelta

import boto3
import pytest

from handlers import aggregate as aggregate_handler
from handlers import ingest, pipeline_status, process
from helpers import make_job
from sajobs.repository import Repository


def sqs_event(messages):
    return {
        "Records": [
            {
                "messageId": m.get("MessageId", f"m{i}"),
                "body": m["Body"],
                "attributes": m.get("Attributes", {"ApproximateReceiveCount": "1"}),
            }
            for i, m in enumerate(messages)
        ]
    }


def read_gz(cloud, key):
    body = cloud.s3.get_object(Bucket="sa-jobmarket-data-test", Key=key)["Body"].read()
    return [json.loads(line) for line in gzip.decompress(body).decode().splitlines() if line]


def test_ingest_uses_sample_when_requested(cloud):
    result = ingest.handler({"execution_id": "exec-1", "input": {"use_sample": True}})
    assert result["source"] == "sample" and result["fetched"] == result["queued"] == 36
    raw_keys = cloud.keys("raw/adzuna/ingest_date=")
    assert len(raw_keys) == 1 and raw_keys[0].endswith("/exec-1.jsonl.gz")
    assert len(read_gz(cloud, raw_keys[0])) == 36
    messages = cloud.queue_messages()
    assert len(messages) == 36
    body = json.loads(messages[0]["Body"])
    assert body["execution_id"] == "exec-1" and body["job"]["source"] == "adzuna"
    run = Repository(cloud.table).get_run("exec-1")
    assert (run["status"], run["fetched"], run["new_jobs"], run["source"]) == ("RUNNING", 36, 0, "sample")


def test_ingest_falls_back_to_sample_when_keys_missing(cloud):
    result = ingest.handler({"execution_id": "exec-2", "use_sample": False})
    assert result["source"] == "sample"


def test_ingest_uses_adzuna_when_keys_present(cloud, monkeypatch):
    cloud.ssm.put_parameter(Name="/sa-jobmarket/adzuna/app_id", Value="id", Type="SecureString")
    cloud.ssm.put_parameter(Name="/sa-jobmarket/adzuna/app_key", Value="key", Type="SecureString")
    monkeypatch.setenv("SEARCH_TERMS", "data engineer, devops")
    seen = {}

    class FakeClient:
        def __init__(self, app_id, app_key, **kwargs):
            seen.update(app_id=app_id, app_key=app_key, **kwargs)
            self.calls, self.errors = 2, []

        def fetch(self):
            yield {"id": "1", "title": "Data Engineer"}, "data engineer"
            yield {"id": "2", "title": ""}, "devops"  # rejected: blank title

    monkeypatch.setattr(ingest, "AdzunaClient", FakeClient)
    result = ingest.handler({"execution_id": "exec-3"})
    assert (result["source"], result["fetched"], result["queued"], result["rejected"]) == ("adzuna", 2, 1, 1)
    assert seen["app_key"] == "key" and seen["search_terms"] == ("data engineer", "devops")


def test_ingest_raises_when_adzuna_fails_completely(cloud, monkeypatch):
    cloud.ssm.put_parameter(Name="/sa-jobmarket/adzuna/app_id", Value="id", Type="SecureString")
    cloud.ssm.put_parameter(Name="/sa-jobmarket/adzuna/app_key", Value="key", Type="SecureString")

    class Broken:
        def __init__(self, *a, **k):
            self.calls, self.errors = 1, ["HTTP 401"]

        def fetch(self):
            return iter(())

    monkeypatch.setattr(ingest, "AdzunaClient", Broken)
    with pytest.raises(ingest.AdzunaError):
        ingest.handler({"execution_id": "exec-4"})


def test_ingest_ssm_error_falls_back(cloud, monkeypatch):
    from botocore.exceptions import ClientError

    def denied(**kwargs):
        raise ClientError({"Error": {"Code": "AccessDeniedException", "Message": "no"}}, "GetParameters")

    monkeypatch.setattr(ingest.aws.client("ssm"), "get_parameters", denied)
    assert ingest._adzuna_keys() is None


def test_full_pipeline_process_and_aggregate(cloud):
    ingest.handler({"execution_id": "exec-1", "input": {"use_sample": True}})
    messages = cloud.queue_messages()
    bad = {"MessageId": "bad", "Body": "not json", "Attributes": {"ApproximateReceiveCount": "3"}}
    result = process.handler(sqs_event([*messages[:30], bad]))
    assert result == {"batchItemFailures": [{"itemIdentifier": "bad"}]}
    process.handler(sqs_event(messages[30:]))
    # replaying the same messages inserts nothing new (conditional put) but refreshes the TTL
    process.handler(sqs_event(messages[:5]))

    run = Repository(cloud.table).get_run("exec-1")
    assert (run["new_jobs"], run["failed"]) == (36, 0)  # the bad message has no execution id

    curated = cloud.keys("curated/")
    assert len(curated) == 3
    rows = read_gz(cloud, curated[0])
    assert {"job_id", "skills", "province", "seen_at", "salary_min_zar"} <= set(rows[0])
    assert "description" not in rows[0]

    job = Repository(cloud.table).get_job(rows[0]["job_id"])
    assert job["job_id"] == rows[0]["job_id"]

    summary = aggregate_handler.handler({})
    assert summary["total_jobs"] == 36 and summary["records"] == 41
    repo = Repository(cloud.table)
    assert repo.get_stats("OVERVIEW")["total_jobs"] == 36
    assert repo.get_stats("TRENDS")["weeks"][0]["week"] == summary["week"]
    assert repo.get_weekly_snapshot(summary["week"])["total_jobs"] == 36


def test_process_counts_final_failures_per_execution(cloud):
    body = json.dumps({"execution_id": "exec-9", "job": {"source": "adzuna"}})  # missing title
    repo = Repository(cloud.table)
    repo.start_run("exec-9", fetched=1, source="sample", started_at="2026-10-09T05:00:00Z")
    first = process.handler(sqs_event([{"MessageId": "x", "Body": body}]))
    assert first["batchItemFailures"] == [{"itemIdentifier": "x"}]
    assert repo.get_run("exec-9")["failed"] == 0
    process.handler(sqs_event([{"MessageId": "x", "Body": body, "Attributes": {"ApproximateReceiveCount": "3"}}]))
    assert repo.get_run("exec-9")["failed"] == 1


def test_process_reports_storage_failures(cloud, monkeypatch):
    body = json.dumps({"execution_id": "e", "job": make_job().to_dict()})

    def broken(self, item):
        raise RuntimeError("throttled")

    monkeypatch.setattr(Repository, "put_job_if_new", broken)
    result = process.handler(sqs_event([{"MessageId": "m1", "Body": body}]))
    assert result["batchItemFailures"] == [{"itemIdentifier": "m1"}]


def _put_curated(cloud, day, name, rows):
    body = gzip.compress(("\n".join(json.dumps(r) for r in rows) + "\n\n{corrupt\n").encode())
    cloud.s3.put_object(Bucket="sa-jobmarket-data-test", Key=f"curated/date={day}/{name}.jsonl.gz", Body=body)


def test_aggregate_compacts_finished_days_and_ignores_old_files(cloud):
    now = datetime.now(UTC)
    yesterday = (now - timedelta(days=1)).strftime("%Y-%m-%d")
    today = now.strftime("%Y-%m-%d")
    old = (now - timedelta(days=60)).strftime("%Y-%m-%d")
    seen = (now - timedelta(days=1)).strftime("%Y-%m-%dT%H:%M:%SZ")
    row = {"job_id": "a", "skills": ["SQL"], "province": "Gauteng", "seen_at": seen}
    _put_curated(cloud, yesterday, "one", [row])
    _put_curated(cloud, yesterday, "two", [row, {**row, "job_id": "b"}])
    _put_curated(cloud, today, "one", [{**row, "job_id": "c"}])
    _put_curated(cloud, today, "two", [{**row, "job_id": "d"}])
    _put_curated(cloud, old, "one", [{**row, "job_id": "z"}])

    summary = aggregate_handler.handler({})
    assert summary["total_jobs"] == 4 and summary["files"] == 4

    yesterday_keys = cloud.keys(f"curated/date={yesterday}/")
    assert len(yesterday_keys) == 1 and "compacted-" in yesterday_keys[0]
    assert {r["job_id"] for r in read_gz(cloud, yesterday_keys[0])} == {"a", "b"}
    assert len(cloud.keys(f"curated/date={today}/")) == 2

    # second run reads the compacted file and keeps the previous TRENDS weeks
    assert aggregate_handler.handler({})["files"] == 3


def _distribution(cloud) -> str:
    cf = boto3.client("cloudfront")
    return cf.create_distribution(
        DistributionConfig={
            "CallerReference": "test",
            "Comment": "",
            "Enabled": True,
            "Origins": {
                "Quantity": 1,
                "Items": [
                    {"Id": "web", "DomainName": "web.s3.amazonaws.com", "S3OriginConfig": {"OriginAccessIdentity": ""}}
                ],
            },
            "DefaultCacheBehavior": {
                "TargetOriginId": "web",
                "ViewerProtocolPolicy": "redirect-to-https",
                "MinTTL": 0,
                "ForwardedValues": {"QueryString": False, "Cookies": {"Forward": "none"}},
            },
        }
    )["Distribution"]["Id"]


def test_aggregate_invalidates_public_api_cache(cloud, monkeypatch):
    distribution_id = _distribution(cloud)
    monkeypatch.setenv("DISTRIBUTION_ID", distribution_id)
    summary = aggregate_handler.handler({})

    assert summary["invalidation_id"]
    cf = boto3.client("cloudfront")
    invalidation = cf.get_invalidation(DistributionId=distribution_id, Id=summary["invalidation_id"])["Invalidation"]
    assert invalidation["InvalidationBatch"]["Paths"]["Items"] == ["/api/public/*"]
    assert invalidation["InvalidationBatch"]["CallerReference"].startswith("aggregate-")


def test_aggregate_skips_invalidation_without_distribution(cloud, monkeypatch):
    monkeypatch.delenv("DISTRIBUTION_ID", raising=False)
    assert aggregate_handler.handler({})["invalidation_id"] is None


def test_aggregate_invalidation_failure_is_not_fatal(cloud, monkeypatch, caplog):
    monkeypatch.setenv("DISTRIBUTION_ID", "EDOESNOTEXIST")
    summary = aggregate_handler.handler({})

    assert summary["invalidation_id"] is None
    assert Repository(cloud.table).get_stats("OVERVIEW") is not None  # stats were still written
    assert "CloudFront invalidation failed" in caplog.text


def test_pipeline_status_check_queue_and_mark(cloud):
    empty = pipeline_status.handler({"action": "check_queue", "polls": 0})
    assert empty == {"pending": 0, "polls": 1, "wait_seconds": 20}
    cloud.sqs.send_message(QueueUrl=cloud.queue_url, MessageBody="x")
    assert pipeline_status.handler({"action": "check_queue"})["pending"] == 1

    repo = Repository(cloud.table)
    repo.start_run("exec-1", fetched=3, source="sample", started_at="2026-10-09T05:00:00Z")
    out = pipeline_status.handler({"action": "mark", "execution_id": "exec-1", "status": "SUCCEEDED"})
    assert out["status"] == "SUCCEEDED" and repo.get_run("exec-1")["status"] == "SUCCEEDED"

    error = {"Error": "States.TaskFailed", "Cause": json.dumps({"errorMessage": "boom"})}
    pipeline_status.handler({"action": "mark", "execution_id": "exec-2", "status": "FAILED", "error": error})
    assert repo.get_run("exec-2")["error"] == "States.TaskFailed: boom"
    pipeline_status.handler({"action": "mark", "execution_id": "exec-3", "status": "FAILED", "error": "plain"})
    assert repo.get_run("exec-3")["error"] == "plain"

    with pytest.raises(ValueError):
        pipeline_status.handler({"action": "mark", "execution_id": "x", "status": "WEIRD"})
    with pytest.raises(ValueError):
        pipeline_status.handler({"action": "dance"})


def test_wait_seconds_grow_with_backlog(cloud, monkeypatch):
    class FakeSqs:
        def get_queue_attributes(self, **kwargs):
            return {"Attributes": {"ApproximateNumberOfMessages": "5000", "ApproximateNumberOfMessagesNotVisible": "0",
                                   "ApproximateNumberOfMessagesDelayed": "0"}}

    monkeypatch.setattr(pipeline_status.aws, "client", lambda name: FakeSqs())
    assert pipeline_status.check_queue(3) == {"pending": 5000, "polls": 4, "wait_seconds": 120}
