"""Every API route's real output checked field by field against docs/api-contract.md.

The fixtures below are transcribed from the contract (and mirror ``frontend/src/api/types.ts``), not from the
handlers, so a renamed, missing, extra or wrongly-nullable field fails here. Keep all three in step.
"""
from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import pytest

from conftest import ADMIN, USER_A, api_event, body_of
from handlers import api_admin, api_me, api_public
from helpers import curated, make_job, sample_records, seed_jobs
from sajobs.aggregate import compute_stats
from sajobs.repository import Repository

NOW = datetime.now(UTC)


class Nullable:
    def __init__(self, spec: Any):
        self.spec = spec


class ListOf:
    def __init__(self, spec: Any, length: int | None = None):
        self.spec = spec
        self.length = length


ISO = "iso-datetime"
PROVINCE = frozenset(
    {
        "Gauteng", "Western Cape", "KwaZulu-Natal", "Eastern Cape", "Free State",
        "Limpopo", "Mpumalanga", "North West", "Northern Cape", "Remote", "Unknown",
    }
)
SENIORITY = frozenset({"intern", "junior", "mid", "senior", "lead", "unspecified"})
EMPLOYMENT = frozenset({"full_time", "part_time", "contract", "internship", "temporary", "unspecified"})
SUBSCRIPTION = frozenset({"none", "pending_confirmation", "confirmed"})
RUN_STATUS = frozenset({"RUNNING", "SUCCEEDED", "FAILED", "TIMED_OUT", "ABORTED"})
ERROR_CODE = frozenset({"bad_request", "unauthorized", "forbidden", "not_found", "limit_reached", "internal"})

NUMBER = (int, float)
SKILL_COUNT = {"skill": str, "count": int}

OVERVIEW = {
    "last_updated": Nullable(ISO),
    "window_days": int,
    "total_jobs": int,
    "new_this_week": int,
    "median_salary_zar": Nullable(NUMBER),
    "top_skill": Nullable(str),
    "top_province": Nullable(PROVINCE),
    "seniority": ListOf({"name": SENIORITY, "count": int}),
    "employment_type": ListOf({"name": EMPLOYMENT, "count": int}),
}
SKILLS = {
    "last_updated": Nullable(ISO),
    "skills": ListOf({"skill": str, "category": str, "count": int, "share": NUMBER, "change_vs_prev_week": int}),
}
SKILL_LIST = {"skills": ListOf({"name": str, "category": str})}
SALARIES = {
    "last_updated": Nullable(ISO),
    "salaries": ListOf({"skill": str, "sample_size": int, "p25": NUMBER, "median": NUMBER, "p75": NUMBER}),
}
PROVINCES = {
    "last_updated": Nullable(ISO),
    "provinces": ListOf(
        {"province": PROVINCE, "count": int, "median_salary_zar": Nullable(NUMBER), "top_skills": ListOf(SKILL_COUNT)}
    ),
}
PAIRS = {"last_updated": Nullable(ISO), "pairs": ListOf({"skills": ListOf(str, length=2), "count": int})}
TRENDS = {
    "last_updated": Nullable(ISO),
    "weeks": ListOf({"week": str, "total_jobs": int, "top_skills": ListOf(SKILL_COUNT)}),
}
JOB = {
    "job_id": str,
    "title": str,
    "company": str,
    "location": Nullable(str),
    "city": Nullable(str),
    "province": PROVINCE,
    "is_remote": bool,
    "salary_min_zar": Nullable(NUMBER),
    "salary_max_zar": Nullable(NUMBER),
    "salary_is_predicted": bool,
    "seniority": SENIORITY,
    "employment_type": EMPLOYMENT,
    "experience_years_min": Nullable(int),
    "experience_years_max": Nullable(int),
    "skills": ListOf(str),
    "date_posted": Nullable(str),
    "url": Nullable(str),
    "source": str,
    "description_snippet": str,
}
JOBS_PAGE = {"items": ListOf(JOB), "next_cursor": Nullable(str)}
SAVED_JOB = {"job_id": str, "title": str, "company": str, "province": PROVINCE, "saved_at": ISO}
SAVED_JOBS = {"items": ListOf(SAVED_JOB)}
ALERT = {"alert_id": str, "skills": ListOf(str), "province": Nullable(PROVINCE), "created_at": ISO}
ALERTS = {"email": str, "subscription_status": SUBSCRIPTION, "alerts": ListOf(ALERT)}
CREATE_ALERT = {"alert": ALERT, "subscription_status": SUBSCRIPTION}
START_RUN = {"execution_id": str, "started_at": ISO}
RUNS = {
    "dlq_depth": int,
    "runs": ListOf(
        {
            "execution_id": str,
            "status": RUN_STATUS,
            "started_at": ISO,
            "stopped_at": Nullable(ISO),
            "fetched": Nullable(int),
            "new_jobs": Nullable(int),
            "failed": Nullable(int),
        }
    ),
}
ERROR = {"error": {"code": ERROR_CODE, "message": str}}


def check(value: Any, spec: Any, where: str = "$") -> None:
    if isinstance(spec, Nullable):
        if value is not None:
            check(value, spec.spec, where)
    elif isinstance(spec, dict):
        assert isinstance(value, dict), f"{where}: expected object, got {value!r}"
        assert set(value) == set(spec), f"{where}: keys {sorted(value)} != contract {sorted(spec)}"
        for key, sub in spec.items():
            check(value[key], sub, f"{where}.{key}")
    elif isinstance(spec, ListOf):
        assert isinstance(value, list), f"{where}: expected list, got {value!r}"
        if spec.length is not None:
            assert len(value) == spec.length, f"{where}: expected {spec.length} items"
        for i, item in enumerate(value):
            check(item, spec.spec, f"{where}[{i}]")
    elif isinstance(spec, frozenset):
        assert value in spec, f"{where}: {value!r} is not one of the contract values"
    elif spec == ISO:
        assert isinstance(value, str) and value.endswith("Z"), f"{where}: expected ISO UTC string, got {value!r}"
        datetime.fromisoformat(value)
    elif spec is int:
        assert isinstance(value, int) and not isinstance(value, bool), f"{where}: expected int, got {value!r}"
    elif spec == NUMBER:
        assert isinstance(value, NUMBER) and not isinstance(value, bool), f"{where}: expected number, got {value!r}"
    else:
        assert isinstance(value, spec), f"{where}: expected {spec.__name__}, got {value!r}"


def expect(response: dict[str, Any], status: int, spec: Any, cache: str) -> Any:
    assert response["statusCode"] == status, response.get("body")
    assert response["headers"]["Cache-Control"] == cache
    body = body_of(response)
    if status == 204:
        assert body is None
    else:
        assert response["headers"]["Content-Type"].startswith("application/json")
        check(body, spec)
    return body


PUBLIC = "public, max-age=900"
PRIVATE = "no-store"


def public(path: str, query: dict[str, str] | None = None, job_id: str | None = None) -> dict[str, Any]:
    if job_id is not None:
        return api_public.handler(api_event("GET /api/public/jobs/{job_id}", path={"job_id": job_id}))
    return api_public.handler(api_event(f"GET {path}", query=query))


def me(route: str, claims=USER_A, **kwargs) -> dict[str, Any]:
    return api_me.handler(api_event(route, claims=claims, **kwargs))


def admin(route: str, claims=ADMIN) -> dict[str, Any]:
    return api_admin.handler(api_event(route, claims=claims))


PUBLIC_STATS = [
    ("/api/public/overview", OVERVIEW),
    ("/api/public/skills", SKILLS),
    ("/api/public/skill-list", SKILL_LIST),
    ("/api/public/salaries", SALARIES),
    ("/api/public/provinces", PROVINCES),
    ("/api/public/skill-pairs", PAIRS),
    ("/api/public/trends", TRENDS),
    ("/api/public/jobs", JOBS_PAGE),
]


@pytest.mark.parametrize("path, spec", PUBLIC_STATS)
def test_public_routes_before_first_run(cloud, path, spec):
    body = expect(public(path), 200, spec, PUBLIC)
    if "last_updated" in spec:
        assert body["last_updated"] is None
    if path.endswith("/overview"):
        assert body["top_skill"] is None and body["top_province"] is None and body["median_salary_zar"] is None


@pytest.fixture
def seeded(cloud):
    records = sample_records(NOW)
    sparse = {**curated(make_job(source_id="sparse"), NOW), "company": None, "location": None, "url": None}
    seed_jobs(cloud.table, NOW, [*records, sparse])
    result = compute_stats(records, NOW)
    Repository(cloud.table).put_stats(result["sections"], result["week"], result["snapshot"], NOW)
    return records


@pytest.mark.parametrize("path, spec", PUBLIC_STATS)
def test_public_routes_after_a_run(seeded, path, spec):
    body = expect(public(path), 200, spec, PUBLIC)
    if "last_updated" in spec:
        assert body["last_updated"] is not None
    assert any(isinstance(v, list) and v for v in body.values()), "seeded response should not be empty"


@pytest.mark.parametrize(
    "path, query, spec",
    [
        ("/api/public/salaries", {"skill": "python"}, SALARIES),
        ("/api/public/salaries", {"skill": "Klingon"}, SALARIES),
        ("/api/public/jobs", {"skill": "python", "province": "gauteng", "limit": "2"}, JOBS_PAGE),
        ("/api/public/jobs", {"skill": "Klingon"}, JOBS_PAGE),
    ],
)
def test_public_filters(seeded, path, query, spec):
    expect(public(path, query), 200, spec, PUBLIC)


def test_job_detail_and_nullable_job_fields(seeded):
    page = expect(public("/api/public/jobs", {"limit": "50"}), 200, JOBS_PAGE, PUBLIC)
    while page["next_cursor"]:
        query = {"limit": "50", "cursor": page["next_cursor"]}
        more = expect(public("/api/public/jobs", query), 200, JOBS_PAGE, PUBLIC)
        page = {"items": page["items"] + more["items"], "next_cursor": more["next_cursor"]}
    sparse = next(j for j in page["items"] if j["location"] is None)
    assert sparse["company"] == "" and sparse["url"] is None
    expect(public("", job_id=sparse["job_id"]), 200, JOB, PUBLIC)


@pytest.mark.parametrize(
    "query, job_id, status",
    [
        ({"limit": "0"}, None, 400),
        ({"limit": "abc"}, None, 400),
        ({"province": "Atlantis"}, None, 400),
        ({"cursor": "not-a-cursor"}, None, 400),
        (None, "0" * 40, 404),
    ],
)
def test_public_errors_are_not_cached(cloud, query, job_id, status):
    expect(public("/api/public/jobs", query, job_id), status, ERROR, PRIVATE)


def test_me_routes(seeded):
    job_id = public("/api/public/jobs", {"limit": "1"})
    job_id = body_of(job_id)["items"][0]["job_id"]

    expect(me("GET /api/me/saved-jobs"), 200, SAVED_JOBS, PRIVATE)
    expect(me("PUT /api/me/saved-jobs/{job_id}", path={"job_id": job_id}), 200, SAVED_JOB, PRIVATE)
    saved = expect(me("GET /api/me/saved-jobs"), 200, SAVED_JOBS, PRIVATE)
    assert [s["job_id"] for s in saved["items"]] == [job_id]
    expect(me("DELETE /api/me/saved-jobs/{job_id}", path={"job_id": job_id}), 204, None, PRIVATE)

    empty = expect(me("GET /api/me/alerts"), 200, ALERTS, PRIVATE)
    assert empty["subscription_status"] == "none"
    anywhere = expect(me("POST /api/me/alerts", body={"skills": ["python"]}), 201, CREATE_ALERT, PRIVATE)
    assert anywhere["alert"]["province"] is None and anywhere["alert"]["skills"] == ["Python"]
    local = expect(
        me("POST /api/me/alerts", body={"skills": ["AWS"], "province": "Gauteng"}), 201, CREATE_ALERT, PRIVATE
    )
    assert local["alert"]["province"] == "Gauteng"
    listed = expect(me("GET /api/me/alerts"), 200, ALERTS, PRIVATE)
    assert [a["province"] for a in listed["alerts"]] == [None, "Gauteng"]
    alert_id = local["alert"]["alert_id"]
    expect(me("DELETE /api/me/alerts/{alert_id}", path={"alert_id": alert_id}), 204, None, PRIVATE)
    expect(me("DELETE /api/me"), 204, None, PRIVATE)


def test_alerts_email_is_a_string_even_without_an_email_claim(cloud):
    body = expect(me("GET /api/me/alerts", claims={"sub": USER_A["sub"]}), 200, ALERTS, PRIVATE)
    assert body["email"] == ""


@pytest.mark.parametrize(
    "route, kwargs, status",
    [
        ("PUT /api/me/saved-jobs/{job_id}", {"path": {"job_id": "0" * 40}}, 404),
        ("POST /api/me/alerts", {"body": {"skills": []}}, 400),
        ("POST /api/me/alerts", {"body": {"skills": ["Python"], "province": "Atlantis"}}, 400),
        ("GET /api/me/alerts", {"claims": None}, 401),
    ],
)
def test_me_errors(cloud, route, kwargs, status):
    expect(me(route, **{"claims": USER_A, **kwargs}), status, ERROR, PRIVATE)


def test_me_alert_limit_is_409(cloud):
    for _ in range(5):
        assert me("POST /api/me/alerts", body={"skills": ["SQL"]})["statusCode"] == 201
    expect(me("POST /api/me/alerts", body={"skills": ["SQL"]}), 409, ERROR, PRIVATE)


def test_admin_routes(cloud):
    expect(admin("GET /api/admin/runs"), 200, RUNS, PRIVATE)
    started = expect(admin("POST /api/admin/runs"), 202, START_RUN, PRIVATE)
    Repository(cloud.table).start_run(
        started["execution_id"], fetched=12, source="sample", started_at=started["started_at"]
    )
    runs = expect(admin("GET /api/admin/runs"), 200, RUNS, PRIVATE)
    assert runs["runs"][0]["execution_id"] == started["execution_id"] and runs["runs"][0]["fetched"] == 12


def test_admin_errors(cloud):
    expect(admin("GET /api/admin/runs", claims=USER_A), 403, ERROR, PRIVATE)
    expect(admin("POST /api/admin/runs", claims=None), 401, ERROR, PRIVATE)
