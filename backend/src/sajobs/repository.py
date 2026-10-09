"""DynamoDB single-table access. Every key pattern in PLAN.md section 7 lives in this module.

| Entity          | PK                  | SK                         |
|-----------------|---------------------|----------------------------|
| Job             | JOB#<job_id>        | META  (+ GSI1 PROV#<province>, GSI2 JOBS) |
| Stats           | STATS#LATEST        | OVERVIEW / SKILLS / ...    |
| Weekly snapshot | STATS#<yyyy-Www>    | SKILLS                     |
| User profile    | USER#<sub>          | PROFILE                    |
| Saved job       | USER#<sub>          | SAVED#<job_id>             |
| Alert           | USER#<sub>          | ALERT#<alert_id>           |
| Alert index     | ALERTIDX#<skill>    | <sub>#<alert_id>           |
| Pipeline run    | RUN#<execution_id>  | META                       |
"""
from __future__ import annotations

import base64
import binascii
import json
import time
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any

from boto3.dynamodb.conditions import Attr, Key
from botocore.exceptions import ClientError

from sajobs.models import PUBLIC_JOB_FIELDS, format_datetime, parse_datetime

JOB_TTL_DAYS = 60
GSI1 = "GSI1"
GSI2 = "GSI2"
SKILL_FILTER_PAGE = 100
SKILL_FILTER_MAX_SCANNED = 300  # bounds one request's reads on the 5-RCU indexes
META = "META"
STATS_LATEST = "STATS#LATEST"


# ------------------------------------------------------------------ keys


def job_key(job_id: str) -> dict[str, str]:
    return {"PK": f"JOB#{job_id}", "SK": META}


def stats_key(section: str) -> dict[str, str]:
    return {"PK": STATS_LATEST, "SK": section}


def weekly_key(week: str) -> dict[str, str]:
    return {"PK": f"STATS#{week}", "SK": "SKILLS"}


def user_pk(sub: str) -> str:
    if not sub:
        raise ValueError("sub is required")
    return f"USER#{sub}"


def profile_key(sub: str) -> dict[str, str]:
    return {"PK": user_pk(sub), "SK": "PROFILE"}


def saved_key(sub: str, job_id: str) -> dict[str, str]:
    return {"PK": user_pk(sub), "SK": f"SAVED#{job_id}"}


def alert_key(sub: str, alert_id: str) -> dict[str, str]:
    return {"PK": user_pk(sub), "SK": f"ALERT#{alert_id}"}


def alert_index_key(skill: str, sub: str, alert_id: str) -> dict[str, str]:
    return {"PK": f"ALERTIDX#{skill}", "SK": f"{sub}#{alert_id}"}


def run_key(execution_id: str) -> dict[str, str]:
    return {"PK": f"RUN#{execution_id}", "SK": META}


# ---------------------------------------------------------- conversions


def to_dynamo(value: Any) -> Any:
    """Recursively convert floats to ``Decimal`` (boto3 rejects floats)."""
    if isinstance(value, bool):
        return value
    if isinstance(value, float):
        return Decimal(str(value))
    if isinstance(value, dict):
        return {k: to_dynamo(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [to_dynamo(v) for v in value]
    return value


def from_dynamo(value: Any) -> Any:
    """Recursively convert ``Decimal`` back to ``int``/``float`` and sets to sorted lists."""
    if isinstance(value, Decimal):
        return int(value) if value == value.to_integral_value() else float(value)
    if isinstance(value, dict):
        return {k: from_dynamo(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [from_dynamo(v) for v in value]
    if isinstance(value, (set, frozenset)):
        return sorted(from_dynamo(v) for v in value)
    return value


def encode_cursor(last_key: dict[str, Any] | None) -> str | None:
    if not last_key:
        return None
    raw = json.dumps(from_dynamo(last_key), separators=(",", ":"), sort_keys=True).encode()
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


def decode_cursor(cursor: str | None, required: set[str]) -> dict[str, str] | None:
    """Decode an opaque cursor; raise ``ValueError`` unless it is a key with exactly ``required`` attributes."""
    if not cursor:
        return None
    try:
        padded = cursor + "=" * (-len(cursor) % 4)
        data = json.loads(base64.urlsafe_b64decode(padded.encode()).decode())
    except (binascii.Error, ValueError, UnicodeDecodeError) as exc:
        raise ValueError("invalid cursor") from exc
    if not isinstance(data, dict) or set(data) != required or not all(isinstance(v, str) for v in data.values()):
        raise ValueError("invalid cursor")
    return data


def public_job(item: dict[str, Any]) -> dict[str, Any]:
    data = from_dynamo(item)
    job = {name: data.get(name) for name in PUBLIC_JOB_FIELDS}
    for name in ("title", "company", "description_snippet", "source"):
        job[name] = job.get(name) or ""
    job["province"] = job.get("province") or "Unknown"
    job["seniority"] = job.get("seniority") or "unspecified"
    job["employment_type"] = job.get("employment_type") or "unspecified"
    job["skills"] = list(job.get("skills") or [])
    job["salary_is_predicted"] = bool(job.get("salary_is_predicted"))
    job["is_remote"] = bool(job.get("is_remote"))
    return job


# ---------------------------------------------------------- repository


class Repository:
    def __init__(self, table: Any):
        self.table = table

    # ---------------------------------------------------------------- jobs

    @staticmethod
    def job_item(job: dict[str, Any], now: datetime) -> dict[str, Any]:
        job_id = job["job_id"]
        province = job.get("province") or "Unknown"
        posted = job.get("date_posted") or job.get("seen_at") or format_datetime(now)
        sort_key = f"{posted}#{job_id}"
        item = {name: job.get(name) for name in PUBLIC_JOB_FIELDS}
        item.update(
            {
                **job_key(job_id),
                "entity": "JOB",
                "province": province,
                "category": job.get("category"),
                "GSI1PK": f"PROV#{province}",
                "GSI1SK": sort_key,
                "GSI2PK": "JOBS",
                "GSI2SK": sort_key,
                "first_seen": format_datetime(now),
                "last_seen": format_datetime(now),
                "ttl": int((now + timedelta(days=JOB_TTL_DAYS)).timestamp()),
            }
        )
        return to_dynamo(item)

    def put_job_if_new(self, item: dict[str, Any]) -> bool:
        """Insert the job only if it does not exist yet; return ``True`` when it was inserted."""
        try:
            self.table.put_item(Item=item, ConditionExpression="attribute_not_exists(PK)")
        except ClientError as exc:
            if exc.response["Error"]["Code"] == "ConditionalCheckFailedException":
                return False
            raise
        return True

    def touch_job(self, item: dict[str, Any], now: datetime) -> None:
        """Push the TTL of an already known job 60 days past ``now`` (it was seen again) and refresh its
        location fields from ``item`` (a fresh ``job_item``) so improved province rules reach stored jobs."""
        self.table.update_item(
            Key={"PK": item["PK"], "SK": item["SK"]},
            UpdateExpression=(
                "SET #ttl = :ttl, last_seen = :now, province = :province, GSI1PK = :gsi1pk, "
                "city = :city, is_remote = :remote"
            ),
            ConditionExpression="attribute_exists(PK)",
            ExpressionAttributeNames={"#ttl": "ttl"},
            ExpressionAttributeValues={
                ":ttl": int((now + timedelta(days=JOB_TTL_DAYS)).timestamp()),
                ":now": format_datetime(now),
                ":province": item["province"],
                ":gsi1pk": item["GSI1PK"],
                ":city": item.get("city"),
                ":remote": bool(item.get("is_remote")),
            },
        )

    def get_job(self, job_id: str) -> dict[str, Any] | None:
        item = self.table.get_item(Key=job_key(job_id)).get("Item")
        return public_job(item) if item else None

    @staticmethod
    def _jobs_index(province: str | None) -> tuple[str, str, str, str]:
        if province:
            return GSI1, "GSI1PK", f"PROV#{province}", "GSI1SK"
        return GSI2, "GSI2PK", "JOBS", "GSI2SK"

    @classmethod
    def jobs_cursor_start(cls, province: str | None, cursor: str | None) -> dict[str, str] | None:
        """Decode a jobs-list cursor; raise ``ValueError`` if it is malformed or belongs to another listing."""
        _, pk_name, pk_value, sk_name = cls._jobs_index(province)
        start = decode_cursor(cursor, {"PK", "SK", pk_name, sk_name})
        if start and start[pk_name] != pk_value:
            raise ValueError("invalid cursor")
        return start

    def list_jobs(
        self, province: str | None = None, skill: str | None = None, limit: int = 20, cursor: str | None = None
    ) -> tuple[list[dict[str, Any]], str | None]:
        index, pk_name, pk_value, sk_name = self._jobs_index(province)
        start = self.jobs_cursor_start(province, cursor)
        kwargs: dict[str, Any] = {
            "IndexName": index,
            "KeyConditionExpression": Key(pk_name).eq(pk_value),
            "ScanIndexForward": False,
            # DynamoDB applies a filter after Limit, so a skill filter reads bigger pages until it has enough matches.
            "Limit": SKILL_FILTER_PAGE if skill else limit,
        }
        if skill:
            kwargs["FilterExpression"] = Attr("skills").contains(skill)
        items: list[dict[str, Any]] = []
        scanned = 0
        while True:
            if start:
                kwargs["ExclusiveStartKey"] = start
            response = self.table.query(**kwargs)
            page = response.get("Items", [])
            start = response.get("LastEvaluatedKey")
            for position, item in enumerate(page):
                items.append(item)
                if len(items) == limit:
                    if position == len(page) - 1 and not start:
                        return [public_job(i) for i in items], None
                    resume = {name: item[name] for name in ("PK", "SK", pk_name, sk_name)}
                    return [public_job(i) for i in items], encode_cursor(resume)
            scanned += response.get("ScannedCount", len(page))
            if not start or scanned >= SKILL_FILTER_MAX_SCANNED:
                return [public_job(i) for i in items], encode_cursor(start)

    # --------------------------------------------------------------- stats

    def put_stats(self, sections: dict[str, dict[str, Any]], week: str, snapshot: dict[str, Any], now: datetime):
        updated = format_datetime(now)
        with self.table.batch_writer() as batch:
            for name, data in sections.items():
                batch.put_item(Item={**stats_key(name), "data": json.dumps(data), "updated_at": updated})
            batch.put_item(Item={**weekly_key(week), "data": json.dumps(snapshot), "updated_at": updated})

    def get_stats(self, section: str) -> dict[str, Any] | None:
        item = self.table.get_item(Key=stats_key(section)).get("Item")
        return json.loads(item["data"]) if item else None

    def get_weekly_snapshot(self, week: str) -> dict[str, Any] | None:
        item = self.table.get_item(Key=weekly_key(week)).get("Item")
        return json.loads(item["data"]) if item else None

    # ---------------------------------------------------------------- runs

    def start_run(self, execution_id: str, *, fetched: int, source: str, started_at: str) -> None:
        self.table.update_item(
            Key=run_key(execution_id),
            UpdateExpression=(
                "SET #status = :running, fetched = :fetched, #source = :source, started_at = :started, "
                "entity = :entity, new_jobs = if_not_exists(new_jobs, :zero), failed = if_not_exists(failed, :zero)"
            ),
            ExpressionAttributeNames={"#status": "status", "#source": "source"},
            ExpressionAttributeValues={
                ":running": "RUNNING",
                ":fetched": fetched,
                ":source": source,
                ":started": started_at,
                ":entity": "RUN",
                ":zero": 0,
            },
        )

    def set_run_queued(self, execution_id: str, queued: int) -> None:
        self.table.update_item(
            Key=run_key(execution_id),
            UpdateExpression="SET #queued = :queued",
            ExpressionAttributeNames={"#queued": "queued"},
            ExpressionAttributeValues={":queued": queued},
        )

    def add_run_counts(self, execution_id: str, *, new_jobs: int = 0, failed: int = 0, processed: int = 0) -> None:
        if not new_jobs and not failed and not processed:
            return
        self.table.update_item(
            Key=run_key(execution_id),
            UpdateExpression="ADD new_jobs :new, failed :failed, #processed :processed",
            ExpressionAttributeNames={"#processed": "processed"},
            ExpressionAttributeValues={":new": new_jobs, ":failed": failed, ":processed": processed},
        )

    def finish_run(self, execution_id: str, status: str, now: datetime, error: str | None = None) -> dict[str, Any]:
        current = self.get_run(execution_id) or {}
        started = parse_datetime(current.get("started_at"))
        names = {"#status": "status"}
        values: dict[str, Any] = {":status": status, ":stopped": format_datetime(now)}
        expression = "SET #status = :status, stopped_at = :stopped"
        if started:
            expression += ", duration_seconds = :duration"
            values[":duration"] = max(0, int((now - started).total_seconds()))
        if error:
            expression += ", #error = :error"
            names["#error"] = "error"
            values[":error"] = error[:1000]
        response = self.table.update_item(
            Key=run_key(execution_id),
            UpdateExpression=expression,
            ExpressionAttributeNames=names,
            ExpressionAttributeValues=values,
            ReturnValues="ALL_NEW",
        )
        return from_dynamo(response["Attributes"])

    def get_run(self, execution_id: str) -> dict[str, Any] | None:
        item = self.table.get_item(Key=run_key(execution_id)).get("Item")
        return from_dynamo(item) if item else None

    # --------------------------------------------------------------- users

    def _query_user(self, sub: str, prefix: str) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        condition = Key("PK").eq(user_pk(sub))
        if prefix:
            condition = condition & Key("SK").begins_with(prefix)
        kwargs: dict[str, Any] = {"KeyConditionExpression": condition}
        while True:
            response = self.table.query(**kwargs)
            items.extend(from_dynamo(i) for i in response.get("Items", []))
            if "LastEvaluatedKey" not in response:
                return items
            kwargs["ExclusiveStartKey"] = response["LastEvaluatedKey"]

    def get_profile(self, sub: str) -> dict[str, Any] | None:
        item = self.table.get_item(Key=profile_key(sub)).get("Item")
        return from_dynamo(item) if item else None

    def put_profile(self, sub: str, email: str | None, subscription_arn: str | None, now: datetime) -> dict:
        existing = self.get_profile(sub) or {}
        item = {
            **profile_key(sub),
            "entity": "PROFILE",
            "email": email,
            "subscription_arn": subscription_arn,
            "created_at": existing.get("created_at") or format_datetime(now),
        }
        self.table.put_item(Item=item)
        return item

    @staticmethod
    def _saved_public(item: dict[str, Any]) -> dict[str, Any]:
        return {
            "job_id": item.get("job_id"),
            "title": item.get("title") or "",
            "company": item.get("company") or "",
            "province": item.get("province") or "Unknown",
            "saved_at": item.get("saved_at"),
        }

    def list_saved(self, sub: str) -> list[dict[str, Any]]:
        items = [self._saved_public(i) for i in self._query_user(sub, "SAVED#")]
        return sorted(items, key=lambda i: i.get("saved_at") or "", reverse=True)

    def save_job(self, sub: str, job: dict[str, Any], now: datetime) -> dict[str, Any]:
        """Idempotent: re-saving keeps the original ``saved_at``."""
        key = saved_key(sub, job["job_id"])
        existing = self.table.get_item(Key=key).get("Item")
        if existing:
            return self._saved_public(from_dynamo(existing))
        item = {
            **key,
            "entity": "SAVED",
            "job_id": job["job_id"],
            "title": job.get("title"),
            "company": job.get("company"),
            "province": job.get("province"),
            "saved_at": format_datetime(now),
        }
        self.table.put_item(Item=item)
        return self._saved_public(item)

    def unsave_job(self, sub: str, job_id: str) -> None:
        self.table.delete_item(Key=saved_key(sub, job_id))

    @staticmethod
    def _alert_public(item: dict[str, Any]) -> dict[str, Any]:
        return {
            "alert_id": item.get("alert_id"),
            "skills": list(item.get("skills") or []),
            "province": item.get("province"),
            "created_at": item.get("created_at"),
        }

    def list_alerts(self, sub: str) -> list[dict[str, Any]]:
        """Oldest first."""
        items = sorted(self._query_user(sub, "ALERT#"), key=lambda i: (i.get("created_at") or "", i.get("seq") or 0))
        return [self._alert_public(i) for i in items]

    def create_alert(self, sub: str, alert_id: str, skills: list[str], province: str | None, now: datetime) -> dict:
        alert = {
            **alert_key(sub, alert_id),
            "entity": "ALERT",
            "alert_id": alert_id,
            "skills": skills,
            "province": province,
            "created_at": format_datetime(now),
            "seq": time.time_ns(),
        }
        with self.table.batch_writer() as batch:
            batch.put_item(Item=alert)
            for skill in skills:
                batch.put_item(
                    Item={
                        **alert_index_key(skill, sub, alert_id),
                        "entity": "ALERTIDX",
                        "sub": sub,
                        "alert_id": alert_id,
                        "skills": skills,
                        "province": province,
                    }
                )
        return self._alert_public(alert)

    def delete_alert(self, sub: str, alert_id: str) -> bool:
        item = self.table.get_item(Key=alert_key(sub, alert_id)).get("Item")
        if not item:
            return False
        with self.table.batch_writer() as batch:
            for skill in item.get("skills") or []:
                batch.delete_item(Key=alert_index_key(skill, sub, alert_id))
            batch.delete_item(Key=alert_key(sub, alert_id))
        return True

    def delete_user(self, sub: str) -> int:
        """Delete every ``USER#<sub>`` item and the user's alert index entries. Returns items deleted."""
        items = self._query_user(sub, "")
        keys = [{"PK": i["PK"], "SK": i["SK"]} for i in items]
        for item in items:
            if item.get("entity") == "ALERT" or str(item["SK"]).startswith("ALERT#"):
                keys.extend(alert_index_key(s, sub, item["alert_id"]) for s in item.get("skills") or [])
        with self.table.batch_writer() as batch:
            for key in keys:
                batch.delete_item(Key=key)
        return len(keys)

    def alerts_for_skill(self, skill: str) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        kwargs: dict[str, Any] = {"KeyConditionExpression": Key("PK").eq(f"ALERTIDX#{skill}")}
        while True:
            response = self.table.query(**kwargs)
            items.extend(from_dynamo(i) for i in response.get("Items", []))
            if "LastEvaluatedKey" not in response:
                return items
            kwargs["ExclusiveStartKey"] = response["LastEvaluatedKey"]
