"""SQS consumer: enrich each job, write the batch as one curated JSONL.gz file, insert only new jobs into
DynamoDB (conditional put) and add the counts to the ``RUN#`` item. Uses partial batch responses."""
from __future__ import annotations

import gzip
import json
import logging
import os
import uuid
from collections import Counter
from typing import Any

from sajobs import aws
from sajobs.models import Job, format_datetime, utc_now
from sajobs.repository import Repository
from sajobs.transform import enrich

log = logging.getLogger(__name__)

CURATED_FIELDS = (
    "job_id", "source", "source_id", "title", "company", "location", "city", "province", "is_remote", "category",
    "search_term", "salary_min_zar", "salary_max_zar", "salary_is_predicted", "salary_period", "seniority",
    "employment_type", "experience_years_min", "experience_years_max", "skills", "date_posted", "url",
    "description_snippet", "ingested_at",
)


def _max_receives() -> int:
    return int(os.environ.get("MAX_RECEIVE_COUNT", "3"))


def handler(event: dict[str, Any], context: Any = None) -> dict[str, Any]:
    now = utc_now()
    seen_at = format_datetime(now)
    repo = Repository(aws.table())
    failures: list[dict[str, str]] = []
    final_failures: Counter = Counter()
    enriched: list[tuple[str, str, dict[str, Any]]] = []

    for record in event.get("Records", []):
        message_id = record["messageId"]
        try:
            body = json.loads(record["body"])
            job = enrich(Job.from_dict(body["job"]))
            curated = {name: getattr(job, name) for name in CURATED_FIELDS}
            curated["seen_at"] = seen_at
            curated["execution_id"] = body.get("execution_id")
            enriched.append((message_id, body.get("execution_id") or "", curated))
        except (KeyError, TypeError, ValueError) as exc:
            log.warning("bad message %s: %s", message_id, exc)
            failures.append({"itemIdentifier": message_id})
            if int(record.get("attributes", {}).get("ApproximateReceiveCount", "1")) >= _max_receives():
                final_failures[_execution_of(record)] += 1

    if enriched:
        key = f"curated/date={now.strftime('%Y-%m-%d')}/{uuid.uuid4().hex}.jsonl.gz"
        payload = "\n".join(json.dumps(c, ensure_ascii=False) for _, _, c in enriched) + "\n"
        aws.client("s3").put_object(
            Bucket=os.environ["DATA_BUCKET"],
            Key=key,
            Body=gzip.compress(payload.encode("utf-8")),
            ContentType="application/x-ndjson",
            ContentEncoding="gzip",
        )

    new_jobs: Counter = Counter()
    for message_id, execution_id, curated in enriched:
        try:
            if repo.put_job_if_new(Repository.job_item(curated, now)):
                new_jobs[execution_id] += 1
            else:
                repo.touch_job(curated["job_id"], now)
        except Exception:
            log.exception("failed to store job %s", curated.get("job_id"))
            failures.append({"itemIdentifier": message_id})

    for execution_id in set(new_jobs) | set(final_failures):
        if execution_id:
            repo.add_run_counts(execution_id, new_jobs=new_jobs[execution_id], failed=final_failures[execution_id])

    log.info("processed=%d new=%d failed=%d", len(enriched), sum(new_jobs.values()), len(failures))
    return {"batchItemFailures": failures}


def _execution_of(record: dict[str, Any]) -> str:
    try:
        return str(json.loads(record["body"]).get("execution_id") or "")
    except (ValueError, AttributeError, KeyError, TypeError):
        return ""
