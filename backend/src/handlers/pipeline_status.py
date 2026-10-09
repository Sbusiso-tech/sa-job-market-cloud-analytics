"""Small Step Functions helper with two actions.

* ``{"action": "check_queue", "polls": n}`` returns ``{"pending": int, "polls": n + 1, "wait_seconds": int}``.
  ``wait_seconds`` grows with the backlog (20..120 s) so a run needs only a few poll iterations, which keeps
  Step Functions state transitions low.
* ``{"action": "mark", "execution_id": ..., "status": "SUCCEEDED"|"FAILED", "error": {...}}`` finalises the
  ``RUN#`` item.
"""
from __future__ import annotations

import contextlib
import json
import logging
import os
from typing import Any

from sajobs import aws
from sajobs.models import utc_now
from sajobs.repository import Repository

log = logging.getLogger(__name__)

MIN_WAIT, MAX_WAIT = 20, 120
MESSAGES_PER_SECOND = 10  # rough processing rate with MaximumConcurrency 2


def check_queue(polls: int) -> dict[str, Any]:
    attributes = aws.client("sqs").get_queue_attributes(
        QueueUrl=os.environ["QUEUE_URL"],
        AttributeNames=[
            "ApproximateNumberOfMessages",
            "ApproximateNumberOfMessagesNotVisible",
            "ApproximateNumberOfMessagesDelayed",
        ],
    )["Attributes"]
    pending = sum(int(v) for v in attributes.values())
    wait = max(MIN_WAIT, min(MAX_WAIT, pending // MESSAGES_PER_SECOND))
    return {"pending": pending, "polls": polls + 1, "wait_seconds": wait}


def _error_text(error: Any) -> str | None:
    if not error:
        return None
    if isinstance(error, dict):
        cause = error.get("Cause") or ""
        with contextlib.suppress(ValueError, AttributeError):
            cause = json.loads(cause).get("errorMessage", cause)
        return f"{error.get('Error', 'Error')}: {cause}"[:1000]
    return str(error)[:1000]


def handler(event: dict[str, Any], context: Any = None) -> dict[str, Any]:
    action = event.get("action")
    if action == "check_queue":
        return check_queue(int(event.get("polls") or 0))
    if action == "mark":
        status = event.get("status")
        if status not in {"SUCCEEDED", "FAILED"}:
            raise ValueError(f"invalid status {status!r}")
        item = Repository(aws.table()).finish_run(
            str(event["execution_id"]), status, utc_now(), _error_text(event.get("error"))
        )
        return {"execution_id": event["execution_id"], "status": status, "new_jobs": item.get("new_jobs")}
    raise ValueError(f"unknown action {action!r}")
