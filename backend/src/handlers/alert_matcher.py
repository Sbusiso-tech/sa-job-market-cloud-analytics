"""DynamoDB Stream consumer (INSERT of ``JOB#`` items only, via the event source filter).

An alert matches a job when the job has ANY of the alert's skills and the alert's province is empty or equals
the job's province. Matches are grouped per user and each user gets ONE digest per batch, published to the
``job-alerts`` topic with a ``user_sub`` message attribute that the user's subscription filter policy selects.
"""
from __future__ import annotations

import logging
import os
from typing import Any

from boto3.dynamodb.types import TypeDeserializer

from sajobs import aws
from sajobs.repository import Repository, from_dynamo

log = logging.getLogger(__name__)

MAX_JOBS_PER_EMAIL = 10
_deserializer = TypeDeserializer()


def _new_jobs(event: dict[str, Any]) -> list[dict[str, Any]]:
    jobs = []
    for record in event.get("Records", []):
        if record.get("eventName") != "INSERT":
            continue
        image = (record.get("dynamodb") or {}).get("NewImage")
        if not image:
            continue
        item = from_dynamo({k: _deserializer.deserialize(v) for k, v in image.items()})
        if str(item.get("PK", "")).startswith("JOB#"):
            jobs.append(item)
    return jobs


def _rand(value: Any) -> str:
    return "R" + f"{int(value):,}".replace(",", " ")


def salary_text(job: dict[str, Any]) -> str:
    low, high = job.get("salary_min_zar"), job.get("salary_max_zar")
    if low is None and high is None:
        return "Salary not stated"
    text = _rand(low or high) if low == high or not (low and high) else f"{_rand(low)} - {_rand(high)}"
    suffix = " per year (estimated)" if job.get("salary_is_predicted") else " per year"
    return text + suffix


def build_digest(jobs: list[dict[str, Any]]) -> tuple[str, str]:
    count = len(jobs)
    subject = f"{count} new job{'s' if count != 1 else ''} match your SA job alerts"
    lines = [f"Hi, {count} new job{'s' if count != 1 else ''} matched your alerts:", ""]
    for job in jobs[:MAX_JOBS_PER_EMAIL]:
        company = job.get("company") or "Company not stated"
        lines += [
            f"* {job.get('title')}",
            f"  {company} | {job.get('province') or 'Unknown'}",
            f"  {salary_text(job)}",
            f"  {job.get('url') or ''}",
            "",
        ]
    if count > MAX_JOBS_PER_EMAIL:
        lines += [f"...and {count - MAX_JOBS_PER_EMAIL} more. See all jobs on the SA Job Market dashboard.", ""]
    lines += ["You receive this because you created a job alert. Delete your alerts in the app to stop these emails."]
    return subject[:100], "\n".join(lines)


def match(jobs: list[dict[str, Any]], repo: Repository) -> dict[str, list[dict[str, Any]]]:
    """Return ``{sub: [jobs]}`` with each job listed once per user."""
    alerts_cache: dict[str, list[dict[str, Any]]] = {}
    per_user: dict[str, dict[str, dict[str, Any]]] = {}
    for job in jobs:
        for skill in job.get("skills") or []:
            if skill not in alerts_cache:
                alerts_cache[skill] = repo.alerts_for_skill(skill)
            for alert in alerts_cache[skill]:
                province = alert.get("province")
                if province and province != job.get("province"):
                    continue
                per_user.setdefault(alert["sub"], {})[job["job_id"]] = job
    return {
        sub: sorted(found.values(), key=lambda j: j.get("date_posted") or "", reverse=True)
        for sub, found in per_user.items()
    }


def handler(event: dict[str, Any], context: Any = None) -> dict[str, Any]:
    jobs = _new_jobs(event)
    if not jobs:
        return {"jobs": 0, "digests": 0}
    matches = match(jobs, Repository(aws.table()))
    sns = aws.client("sns")
    for sub, user_jobs in matches.items():
        subject, message = build_digest(user_jobs)
        sns.publish(
            TopicArn=os.environ["ALERTS_TOPIC_ARN"],
            Subject=subject,
            Message=message,
            MessageAttributes={"user_sub": {"DataType": "String", "StringValue": sub}},
        )
    log.info("jobs=%d digests=%d", len(jobs), len(matches))
    return {"jobs": len(jobs), "digests": len(matches)}
