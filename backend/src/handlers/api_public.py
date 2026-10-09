"""Public, cacheable API routes (``/api/public/*``, no auth)."""
from __future__ import annotations

import re
from typing import Any

from sajobs import aws
from sajobs.aggregate import empty_section
from sajobs.http import PUBLIC_CACHE, ApiError, dispatch, json_response, path_param, query_params
from sajobs.provinces import normalize_province
from sajobs.repository import Repository
from sajobs.skills import canonical_skill, skill_list

JOB_ID = re.compile(r"^[A-Za-z0-9_-]{1,100}$")
MAX_LIMIT = 50
DEFAULT_LIMIT = 20


def _repo() -> Repository:
    return Repository(aws.table())


def _stats(section: str) -> dict[str, Any]:
    return _repo().get_stats(section) or empty_section(section)


def _ok(body: Any) -> dict[str, Any]:
    return json_response(200, body, PUBLIC_CACHE)


def overview(event):
    return _ok(_stats("OVERVIEW"))


def skills(event):
    return _ok(_stats("SKILLS"))


def skill_names(event):
    return _ok({"skills": skill_list()})


def salaries(event):
    data = _stats("SALARIES")
    wanted = query_params(event).get("skill")
    if wanted:
        name = canonical_skill(wanted)
        data = {**data, "salaries": [s for s in data.get("salaries", []) if name and s["skill"] == name]}
    return _ok(data)


def provinces(event):
    return _ok(_stats("PROVINCES"))


def skill_pairs(event):
    return _ok(_stats("PAIRS"))


def trends(event):
    return _ok(_stats("TRENDS"))


def _limit(raw: str | None) -> int:
    if raw in (None, ""):
        return DEFAULT_LIMIT
    try:
        value = int(raw)
    except ValueError as exc:
        raise ApiError(400, "limit must be an integer between 1 and 50") from exc
    if not 1 <= value <= MAX_LIMIT:
        raise ApiError(400, "limit must be an integer between 1 and 50")
    return value


def jobs(event):
    params = query_params(event)
    province = None
    if params.get("province"):
        province = normalize_province(params["province"])
        if province is None:
            raise ApiError(400, "Unknown province")
    limit = _limit(params.get("limit"))
    cursor = params.get("cursor") or None
    if cursor and len(cursor) > 2000:
        raise ApiError(400, "Invalid cursor")
    try:
        Repository.jobs_cursor_start(province, cursor)
    except ValueError as exc:
        raise ApiError(400, "Invalid cursor") from exc
    skill = None
    if params.get("skill"):
        skill = canonical_skill(params["skill"])
        if skill is None:  # no job can carry a skill the taxonomy doesn't know
            return _ok({"items": [], "next_cursor": None})
    items, next_cursor = _repo().list_jobs(province, skill, limit, cursor)
    return _ok({"items": items, "next_cursor": next_cursor})


def job_detail(event):
    job_id = path_param(event, "job_id")
    if not JOB_ID.match(job_id):
        raise ApiError(404, "Job not found")
    job = _repo().get_job(job_id)
    if job is None:
        raise ApiError(404, "Job not found")
    return _ok(job)


ROUTES = {
    "GET /api/public/overview": overview,
    "GET /api/public/skills": skills,
    "GET /api/public/skill-list": skill_names,
    "GET /api/public/salaries": salaries,
    "GET /api/public/provinces": provinces,
    "GET /api/public/skill-pairs": skill_pairs,
    "GET /api/public/trends": trends,
    "GET /api/public/jobs": jobs,
    "GET /api/public/jobs/{job_id}": job_detail,
}


def handler(event: dict[str, Any], context: Any = None) -> dict[str, Any]:
    return dispatch(event, ROUTES)
