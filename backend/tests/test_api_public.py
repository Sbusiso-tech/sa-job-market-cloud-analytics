from datetime import UTC, datetime

import pytest

from conftest import api_event, body_of
from handlers import api_public
from helpers import curated, make_job, sample_records, seed_jobs
from sajobs.aggregate import SECTIONS, compute_stats, empty_section
from sajobs.repository import Repository

NOW = datetime.now(UTC)
STATS_ROUTES = {
    "OVERVIEW": "/api/public/overview",
    "SKILLS": "/api/public/skills",
    "SALARIES": "/api/public/salaries",
    "PROVINCES": "/api/public/provinces",
    "PAIRS": "/api/public/skill-pairs",
    "TRENDS": "/api/public/trends",
}


def call(route_or_path, **kwargs):
    route = route_or_path if route_or_path.startswith("GET ") else f"GET {route_or_path}"
    return api_public.handler(api_event(route, **kwargs))


@pytest.mark.parametrize("section", SECTIONS)
def test_stats_routes_before_first_run_return_empty_shapes(cloud, section):
    response = call(STATS_ROUTES[section])
    assert response["statusCode"] == 200
    assert response["headers"]["Cache-Control"] == "public, max-age=900"
    assert body_of(response) == empty_section(section)


def test_stats_routes_after_aggregation(cloud):
    result = compute_stats(sample_records(NOW), NOW)
    Repository(cloud.table).put_stats(result["sections"], result["week"], result["snapshot"], NOW)
    for section, path in STATS_ROUTES.items():
        assert body_of(call(path)) == result["sections"][section]

    python = body_of(call("/api/public/salaries", query={"skill": "python"}))
    assert [s["skill"] for s in python["salaries"]] == ["Python"]
    rare = body_of(call("/api/public/salaries", query={"skill": "Pega"}))
    assert rare["salaries"] == []
    unknown = call("/api/public/salaries", query={"skill": "Klingon"})
    assert unknown["statusCode"] == 200 and body_of(unknown)["salaries"] == []


def test_skill_list(cloud):
    skills = body_of(call("/api/public/skill-list"))["skills"]
    assert {"name": "SAP", "category": "Enterprise Platform"} in skills


def test_jobs_list_newest_first_with_pagination(cloud):
    seed_jobs(cloud.table, NOW)
    first = body_of(call("/api/public/jobs", query={"limit": "20"}))
    assert len(first["items"]) == 20 and first["next_cursor"]
    dates = [j["date_posted"] for j in first["items"]]
    assert dates == sorted(dates, reverse=True)
    second = body_of(call("/api/public/jobs", query={"cursor": first["next_cursor"]}))
    assert len(second["items"]) == 16 and second["next_cursor"] is None
    ids = {j["job_id"] for j in first["items"]} | {j["job_id"] for j in second["items"]}
    assert len(ids) == 36
    job = first["items"][0]
    assert set(job) == {
        "job_id", "title", "company", "location", "city", "province", "is_remote", "salary_min_zar",
        "salary_max_zar", "salary_is_predicted", "seniority", "employment_type", "experience_years_min",
        "experience_years_max", "skills", "date_posted", "url", "source", "description_snippet",
    }


def test_jobs_filtered_by_province_and_skill(cloud):
    seed_jobs(cloud.table, NOW)
    gauteng = body_of(call("/api/public/jobs", query={"province": "gauteng", "limit": "50"}))
    assert len(gauteng["items"]) == 15 and {j["province"] for j in gauteng["items"]} == {"Gauteng"}
    python = body_of(call("/api/public/jobs", query={"skill": "PYTHON", "limit": "50"}))
    assert python["items"] and all("Python" in j["skills"] for j in python["items"])
    both = body_of(call("/api/public/jobs", query={"province": "Western Cape", "skill": "AWS", "limit": "50"}))
    assert all(j["province"] == "Western Cape" and "AWS" in j["skills"] for j in both["items"])


@pytest.mark.parametrize(
    "query",
    [
        {"limit": "0"},
        {"limit": "51"},
        {"limit": "ten"},
        {"province": "Atlantis"},
        {"cursor": "garbage!!"},
        {"cursor": "x" * 2001},
        {"skill": "Klingon", "cursor": "garbage!!"},
        {"skill": "Klingon", "limit": "0"},
    ],
)
def test_jobs_validation(cloud, query):
    response = call("/api/public/jobs", query=query)
    assert response["statusCode"] == 400
    assert body_of(response)["error"]["code"] == "bad_request"


def test_jobs_unknown_skill_is_an_empty_page(cloud):
    seed_jobs(cloud.table, NOW)
    response = call("/api/public/jobs", query={"skill": "Klingon"})
    assert response["statusCode"] == 200
    assert body_of(response) == {"items": [], "next_cursor": None}


def test_jobs_missing_company_and_snippet_are_empty_strings(cloud):
    record = {**curated(make_job(), NOW), "company": None, "description_snippet": None, "location": None, "url": None}
    seed_jobs(cloud.table, NOW, [record])
    item = body_of(call("/api/public/jobs"))["items"][0]
    assert item["company"] == "" and item["description_snippet"] == ""
    assert item["location"] is None and item["url"] is None


def test_cursor_from_other_province_rejected(cloud):
    seed_jobs(cloud.table, NOW)
    cursor = body_of(call("/api/public/jobs", query={"province": "Gauteng", "limit": "1"}))["next_cursor"]
    response = call("/api/public/jobs", query={"province": "Limpopo", "cursor": cursor})
    assert response["statusCode"] == 400
    response = call("/api/public/jobs", query={"cursor": cursor})
    assert response["statusCode"] == 400


def test_job_detail(cloud):
    records = seed_jobs(cloud.table, NOW)
    job_id = records[0]["job_id"]
    response = call("GET /api/public/jobs/{job_id}", path={"job_id": job_id})
    assert response["statusCode"] == 200 and body_of(response)["job_id"] == job_id
    missing = call("GET /api/public/jobs/{job_id}", path={"job_id": "0" * 40})
    assert missing["statusCode"] == 404 and body_of(missing)["error"]["code"] == "not_found"
    weird = call("GET /api/public/jobs/{job_id}", path={"job_id": "../etc"})
    assert weird["statusCode"] == 404


def test_unknown_route(cloud):
    assert call("/api/public/nope")["statusCode"] == 404
