"""Step 3 of the pipeline: read the last 37 days of curated files, compute the public statistics and store
them as ``STATS#LATEST`` items plus this week's ``STATS#<yyyy-Www>`` snapshot.

Each day's many small files (one per SQS batch) are compacted into a single file on the way, so later runs read
~37 objects instead of thousands (keeps S3 GET requests inside the free tier).
"""
from __future__ import annotations

import gzip
import json
import logging
import os
import uuid
from datetime import timedelta
from typing import Any

from sajobs import aws
from sajobs.aggregate import compute_stats, dedupe_latest
from sajobs.models import utc_now
from sajobs.repository import Repository

log = logging.getLogger(__name__)

PREFIX = "curated/"
LOOKBACK_DAYS = 37
COMPACTED_PREFIX = "compacted-"
INVALIDATION_PATH = "/api/public/*"


def _list_keys(bucket: str, start_after: str) -> dict[str, list[str]]:
    """Return ``{day_prefix: [keys]}`` for curated objects after ``start_after``."""
    s3 = aws.client("s3")
    by_day: dict[str, list[str]] = {}
    for page in s3.get_paginator("list_objects_v2").paginate(Bucket=bucket, Prefix=PREFIX, StartAfter=start_after):
        for obj in page.get("Contents", []):
            key = obj["Key"]
            day = key.rsplit("/", 1)[0] + "/"
            by_day.setdefault(day, []).append(key)
    return by_day


def _read(bucket: str, key: str) -> list[dict[str, Any]]:
    body = aws.client("s3").get_object(Bucket=bucket, Key=key)["Body"].read()
    text = gzip.decompress(body).decode("utf-8")
    records = []
    for line in text.splitlines():
        if line.strip():
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError:
                log.warning("skipping corrupt line in %s", key)
    return records


def _compact(bucket: str, day: str, keys: list[str], records: list[dict[str, Any]], today: str) -> None:
    """Replace a finished day's files with one deduplicated file. Today's folder is left alone (still growing)."""
    if len(keys) < 2 or day.endswith(f"date={today}/"):
        return
    s3 = aws.client("s3")
    merged = dedupe_latest(records)
    body = "\n".join(json.dumps(r, ensure_ascii=False) for r in merged) + "\n"
    new_key = f"{day}{COMPACTED_PREFIX}{uuid.uuid4().hex}.jsonl.gz"
    s3.put_object(
        Bucket=bucket,
        Key=new_key,
        Body=gzip.compress(body.encode("utf-8")),
        ContentType="application/x-ndjson",
        ContentEncoding="gzip",
    )
    for start in range(0, len(keys), 1000):
        s3.delete_objects(
            Bucket=bucket, Delete={"Objects": [{"Key": k} for k in keys[start : start + 1000]], "Quiet": True}
        )


def invalidate_public_api(now_tag: str) -> str | None:
    """Invalidate cached ``/api/public/*`` responses so the dashboard shows the new statistics right away.

    One wildcard path per run (~30 of the 1,000 free invalidation paths a month). Never fails the pipeline.
    """
    distribution_id = os.environ.get("DISTRIBUTION_ID")
    if not distribution_id:
        return None
    try:
        response = aws.client("cloudfront").create_invalidation(
            DistributionId=distribution_id,
            InvalidationBatch={
                "Paths": {"Quantity": 1, "Items": [INVALIDATION_PATH]},
                "CallerReference": f"aggregate-{now_tag}-{uuid.uuid4().hex[:8]}",
            },
        )
    except Exception as exc:  # a cache that is stale for up to 15 minutes is acceptable
        log.warning("CloudFront invalidation failed (stats still saved): %s", exc)
        return None
    return response["Invalidation"]["Id"]


def handler(event: dict[str, Any] | None = None, context: Any = None) -> dict[str, Any]:
    now = utc_now()
    bucket = os.environ["DATA_BUCKET"]
    start_day = (now - timedelta(days=LOOKBACK_DAYS)).strftime("%Y-%m-%d")
    today = now.strftime("%Y-%m-%d")
    records: list[dict[str, Any]] = []
    files = 0
    for day, keys in sorted(_list_keys(bucket, f"{PREFIX}date={start_day}").items()):
        day_records: list[dict[str, Any]] = []
        for key in keys:
            day_records.extend(_read(bucket, key))
        files += len(keys)
        _compact(bucket, day, keys, day_records, today)
        records.extend(day_records)

    repo = Repository(aws.table())
    previous = repo.get_stats("TRENDS") or {}
    result = compute_stats(records, now, previous.get("weeks") or [])
    repo.put_stats(result["sections"], result["week"], result["snapshot"], now)
    overview = result["sections"]["OVERVIEW"]
    summary = {
        "files": files,
        "records": len(records),
        "total_jobs": overview["total_jobs"],
        "new_this_week": overview["new_this_week"],
        "week": result["week"],
        "invalidation_id": invalidate_public_api(now.strftime("%Y%m%dT%H%M%SZ")),
    }
    log.info("aggregate summary %s", json.dumps(summary))
    return summary
