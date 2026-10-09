"""Signed-in user routes (``/api/me/*``). The user's ``sub`` and ``email`` always come from the verified JWT
claims, never from the request, so a user can only read or change their own ``USER#<sub>`` items."""
from __future__ import annotations

import json
import logging
import os
import re
import uuid
from typing import Any

from botocore.exceptions import ClientError

from sajobs import aws
from sajobs.http import (
    ApiError,
    dispatch,
    get_claims,
    json_response,
    no_content,
    parse_json_body,
    path_param,
    require_sub,
)
from sajobs.models import utc_now
from sajobs.provinces import normalize_province
from sajobs.repository import Repository
from sajobs.skills import canonical_skill

log = logging.getLogger(__name__)

MAX_ALERTS = 5
MAX_SKILLS_PER_ALERT = 5
ID_PATTERN = re.compile(r"^[A-Za-z0-9_-]{1,100}$")


def _repo() -> Repository:
    return Repository(aws.table())


def _sub(event: dict[str, Any]) -> str:
    return require_sub(get_claims(event))


def _id(event: dict[str, Any], name: str, label: str) -> str:
    value = path_param(event, name)
    if not ID_PATTERN.match(value):
        raise ApiError(404, f"{label} not found")
    return value


# ------------------------------------------------------------------ SNS


def _subscription_status(arn: str | None) -> str:
    if not arn:
        return "none"
    try:
        attributes = aws.client("sns").get_subscription_attributes(SubscriptionArn=arn)["Attributes"]
    except ClientError as exc:
        log.info("subscription lookup failed: %s", exc.response["Error"]["Code"])
        return "none"
    return "pending_confirmation" if attributes.get("PendingConfirmation") == "true" else "confirmed"


def _subscribe(sub: str, email: str) -> str:
    response = aws.client("sns").subscribe(
        TopicArn=os.environ["ALERTS_TOPIC_ARN"],
        Protocol="email",
        Endpoint=email,
        Attributes={"FilterPolicy": json.dumps({"user_sub": [sub]}), "FilterPolicyScope": "MessageAttributes"},
        ReturnSubscriptionArn=True,
    )
    return response["SubscriptionArn"]


def _unsubscribe(arn: str | None) -> None:
    if not arn or not arn.startswith("arn:"):
        return
    try:
        aws.client("sns").unsubscribe(SubscriptionArn=arn)
    except ClientError as exc:  # pending or already removed subscriptions can't always be deleted
        log.info("unsubscribe ignored: %s", exc.response["Error"]["Code"])


# --------------------------------------------------------------- saved jobs


def list_saved(event):
    return json_response(200, {"items": _repo().list_saved(_sub(event))})


def save_job(event):
    sub = _sub(event)
    job_id = _id(event, "job_id", "Job")
    repo = _repo()
    job = repo.get_job(job_id)
    if job is None:
        raise ApiError(404, "Job not found")
    return json_response(200, repo.save_job(sub, job, utc_now()))


def unsave_job(event):
    sub = _sub(event)
    _repo().unsave_job(sub, _id(event, "job_id", "Job"))
    return no_content()


# ------------------------------------------------------------------ alerts


def list_alerts(event):
    claims = get_claims(event)
    sub = require_sub(claims)
    repo = _repo()
    alerts = repo.list_alerts(sub)
    profile = repo.get_profile(sub) or {}
    status = _subscription_status(profile.get("subscription_arn")) if alerts else "none"
    return json_response(
        200,
        {"email": claims.get("email") or profile.get("email") or "", "subscription_status": status, "alerts": alerts},
    )


def _validate_alert(body: dict[str, Any]) -> tuple[list[str], str | None]:
    raw_skills = body.get("skills")
    if not isinstance(raw_skills, list) or not 1 <= len(raw_skills) <= MAX_SKILLS_PER_ALERT:
        raise ApiError(400, f"skills must be a list of 1 to {MAX_SKILLS_PER_ALERT} skill names")
    skills: list[str] = []
    for raw in raw_skills:
        name = canonical_skill(raw)
        if name is None:
            raise ApiError(400, f"Unknown skill: {str(raw)[:50]}")
        if name not in skills:
            skills.append(name)
    province = body.get("province")
    if province in (None, ""):
        return skills, None
    canonical = normalize_province(province)
    if canonical is None:
        raise ApiError(400, "Unknown province")
    return skills, canonical


def create_alert(event):
    claims = get_claims(event)
    sub = require_sub(claims)
    skills, province = _validate_alert(parse_json_body(event))
    repo = _repo()
    if len(repo.list_alerts(sub)) >= MAX_ALERTS:
        raise ApiError(409, f"You can have at most {MAX_ALERTS} alerts", "limit_reached")

    now = utc_now()
    profile = repo.get_profile(sub) or {}
    arn = profile.get("subscription_arn")
    status = _subscription_status(arn)
    if status == "none":
        email = claims.get("email")
        if not email or "@" not in str(email):
            raise ApiError(400, "Your token has no email claim; sign in again and send the ID token")
        arn = _subscribe(sub, str(email))
        repo.put_profile(sub, str(email), arn, now)
        status = _subscription_status(arn)
    alert = repo.create_alert(sub, uuid.uuid4().hex[:12], skills, province, now)
    return json_response(201, {"alert": alert, "subscription_status": status})


def delete_alert(event):
    sub = _sub(event)
    alert_id = _id(event, "alert_id", "Alert")
    repo = _repo()
    repo.delete_alert(sub, alert_id)
    if not repo.list_alerts(sub):
        profile = repo.get_profile(sub)
        if profile and profile.get("subscription_arn"):
            _unsubscribe(profile["subscription_arn"])
            repo.put_profile(sub, profile.get("email"), None, utc_now())
    return no_content()


def delete_me(event):
    sub = _sub(event)
    repo = _repo()
    profile = repo.get_profile(sub) or {}
    _unsubscribe(profile.get("subscription_arn"))
    repo.delete_user(sub)
    return no_content()


ROUTES = {
    "GET /api/me/saved-jobs": list_saved,
    "PUT /api/me/saved-jobs/{job_id}": save_job,
    "DELETE /api/me/saved-jobs/{job_id}": unsave_job,
    "GET /api/me/alerts": list_alerts,
    "POST /api/me/alerts": create_alert,
    "DELETE /api/me/alerts/{alert_id}": delete_alert,
    "DELETE /api/me": delete_me,
}


def handler(event: dict[str, Any], context: Any = None) -> dict[str, Any]:
    return dispatch(event, ROUTES)
