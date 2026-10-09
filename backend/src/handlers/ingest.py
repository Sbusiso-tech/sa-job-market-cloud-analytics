"""Step 1 of the pipeline: fetch Adzuna ZA jobs (or the bundled sample), store raw JSONL.gz, queue one SQS
message per job and record the ``RUN#<execution_id>`` item.

Input: ``{"execution_id": "...", "input": {"use_sample": bool}}`` (``use_sample`` may also be top level).
"""
from __future__ import annotations

import gzip
import json
import logging
import os
from typing import Any

from botocore.exceptions import ClientError

from sajobs import aws
from sajobs.adzuna import DEFAULT_SEARCH_TERMS, AdzunaClient, AdzunaError, load_sample, to_job
from sajobs.models import format_datetime, utc_now
from sajobs.repository import Repository

log = logging.getLogger(__name__)

SQS_BATCH = 10


def _adzuna_keys() -> tuple[str, str] | None:
    prefix = os.environ.get("ADZUNA_PARAM_PREFIX", "/sa-jobmarket/adzuna").rstrip("/")
    names = [f"{prefix}/app_id", f"{prefix}/app_key"]
    try:
        response = aws.client("ssm").get_parameters(Names=names, WithDecryption=True)
    except ClientError as exc:
        log.warning("could not read Adzuna keys from SSM: %s", exc.response["Error"]["Code"])
        return None
    values = {p["Name"]: p["Value"] for p in response.get("Parameters", [])}
    app_id, app_key = values.get(names[0]), values.get(names[1])
    return (app_id, app_key) if app_id and app_key else None


def _search_terms() -> tuple[str, ...]:
    raw = os.environ.get("SEARCH_TERMS", "")
    terms = tuple(t.strip() for t in raw.split(",") if t.strip())
    return terms or DEFAULT_SEARCH_TERMS


def _fetch(use_sample: bool) -> tuple[str, list[tuple[dict[str, Any], str | None]]]:
    keys = None if use_sample else _adzuna_keys()
    if keys is None:
        if not use_sample:
            log.warning("Adzuna keys missing; falling back to bundled sample data")
        return "sample", [(raw, None) for raw in load_sample()]
    client = AdzunaClient(
        *keys,
        search_terms=_search_terms(),
        max_pages=int(os.environ.get("ADZUNA_MAX_PAGES", "5")),
        max_calls=int(os.environ.get("ADZUNA_MAX_CALLS", "40")),
    )
    results = list(client.fetch())
    log.info("adzuna calls=%d results=%d errors=%d", client.calls, len(results), len(client.errors))
    if not results and client.errors:
        raise AdzunaError(f"Adzuna fetch failed: {client.errors[0]}")
    return "adzuna", results


def _send_messages(queue_url: str, bodies: list[str]) -> int:
    sqs = aws.client("sqs")
    sent = 0
    for start in range(0, len(bodies), SQS_BATCH):
        chunk = bodies[start : start + SQS_BATCH]
        entries = [{"Id": str(i), "MessageBody": body} for i, body in enumerate(chunk)]
        response = sqs.send_message_batch(QueueUrl=queue_url, Entries=entries)
        failed = response.get("Failed") or []
        if failed:
            retry = [e for e in entries if e["Id"] in {f["Id"] for f in failed}]
            response = sqs.send_message_batch(QueueUrl=queue_url, Entries=retry)
            if response.get("Failed"):
                raise RuntimeError(f"{len(response['Failed'])} SQS messages could not be sent")
        sent += len(chunk)
    return sent


def handler(event: dict[str, Any], context: Any = None) -> dict[str, Any]:
    event = event or {}
    options = event.get("input") if isinstance(event.get("input"), dict) else event
    use_sample = bool(options.get("use_sample", event.get("use_sample", False)))
    now = utc_now()
    execution_id = str(event.get("execution_id") or f"local-{now.strftime('%Y%m%dT%H%M%SZ')}")

    source, results = _fetch(use_sample)

    lines, bodies, rejected = [], [], 0
    for raw, term in results:
        lines.append(json.dumps({"search_term": term, "result": raw}, ensure_ascii=False))
        try:
            job = to_job(raw, term)
        except (KeyError, TypeError, ValueError) as exc:
            rejected += 1
            log.warning("rejected Adzuna record id=%s: %s", raw.get("id"), exc)
            continue
        bodies.append(json.dumps({"execution_id": execution_id, "job": job.to_dict()}, ensure_ascii=False))

    raw_key = f"raw/adzuna/ingest_date={now.strftime('%Y-%m-%d')}/{execution_id}.jsonl.gz"
    aws.client("s3").put_object(
        Bucket=os.environ["DATA_BUCKET"],
        Key=raw_key,
        Body=gzip.compress(("\n".join(lines) + "\n").encode("utf-8")),
        ContentType="application/x-ndjson",
        ContentEncoding="gzip",
    )

    repo = Repository(aws.table())
    repo.start_run(execution_id, fetched=len(results), source=source, started_at=format_datetime(now))
    queued = _send_messages(os.environ["QUEUE_URL"], bodies)
    repo.set_run_queued(execution_id, queued)
    summary = {
        "execution_id": execution_id,
        "source": source,
        "fetched": len(results),
        "queued": queued,
        "rejected": rejected,
        "raw_key": raw_key,
    }
    log.info("ingest summary %s", json.dumps(summary))
    return summary
