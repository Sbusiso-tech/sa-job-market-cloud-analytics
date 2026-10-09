import io
import json
import urllib.error
import urllib.parse
from datetime import UTC, datetime

import pytest

from sajobs.adzuna import (
    DEFAULT_SEARCH_TERMS,
    RESULTS_PER_PAGE,
    AdzunaClient,
    AdzunaError,
    load_sample,
    to_job,
)
from sajobs.models import parse_datetime


class FakeResponse(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def page(n, start=0):
    return {"results": [{"id": str(start + i), "title": f"Job {start + i}"} for i in range(n)]}


class FakeOpener:
    """Returns queued responses; an ``int`` entry raises that HTTP status, an exception instance is raised."""

    def __init__(self, responses):
        self.responses = list(responses)
        self.requests = []

    def __call__(self, request, timeout=None):
        self.requests.append(request.full_url)
        item = self.responses.pop(0)
        if isinstance(item, int):
            headers = {"Retry-After": "1"} if item == 429 else {}
            raise urllib.error.HTTPError(request.full_url, item, "err", headers, None)
        if isinstance(item, Exception):
            raise item
        if isinstance(item, bytes):
            return FakeResponse(item)
        return FakeResponse(json.dumps(item).encode())


class Clock:
    def __init__(self):
        self.now = 0.0
        self.sleeps = []

    def sleep(self, seconds):
        self.sleeps.append(seconds)
        self.now += seconds

    def __call__(self):
        return self.now


def client(opener, **kwargs):
    clock = Clock()
    return AdzunaClient("id", "key", opener=opener, sleep=clock.sleep, clock=clock, **kwargs), clock


def test_default_search_terms_match_plan():
    assert len(DEFAULT_SEARCH_TERMS) == 8 and "data engineer" in DEFAULT_SEARCH_TERMS


def test_fetch_paginates_dedupes_and_stops_on_short_page():
    opener = FakeOpener([page(RESULTS_PER_PAGE), page(3, start=RESULTS_PER_PAGE), page(2)])
    c, clock = client(opener, search_terms=["data engineer", "devops"])
    results = list(c.fetch())
    assert len(results) == RESULTS_PER_PAGE + 3  # ids 0 and 1 of "devops" are duplicates
    assert results[0][1] == "data engineer"
    assert c.calls == 3
    query = urllib.parse.parse_qs(urllib.parse.urlparse(opener.requests[0]).query)
    assert query["what"] == ["data engineer"] and query["results_per_page"] == ["50"]
    assert "/jobs/za/search/1" in opener.requests[0] and "/search/2" in opener.requests[1]
    # pacing: 25 calls/minute => at least 2.4 s between calls
    assert all(s == pytest.approx(2.4) for s in clock.sleeps)


def test_retries_429_and_5xx_with_backoff():
    opener = FakeOpener([429, 503, page(1)])
    c, clock = client(opener, search_terms=["x"])
    assert len(list(c.fetch())) == 1
    assert c.calls == 3
    assert 1.0 in clock.sleeps and 4.0 in clock.sleeps  # Retry-After honoured, then exponential backoff


def test_gives_up_after_retries_and_records_error():
    opener = FakeOpener([500, 500, 500, 500, page(1)])
    c, _ = client(opener, search_terms=["x", "y"], max_retries=3)
    results = list(c.fetch())
    assert len(results) == 1 and len(c.errors) == 1


def test_non_retryable_error_and_network_error():
    c, _ = client(FakeOpener([401, urllib.error.URLError("down"), page(0)]), search_terms=["a", "b"], max_retries=1)
    assert list(c.fetch()) == []
    assert len(c.errors) == 1 and "HTTP 401" in c.errors[0]


def test_invalid_json_is_an_error():
    c, _ = client(FakeOpener([b"not json"]), search_terms=["a"])
    assert list(c.fetch()) == []
    assert "invalid JSON" in c.errors[0]


def test_hard_cap_on_calls():
    opener = FakeOpener([page(RESULTS_PER_PAGE, start=i * 100) for i in range(10)])
    c, _ = client(opener, search_terms=["a", "b", "c"], max_pages=5, max_calls=4)
    results = list(c.fetch())
    assert c.calls == 4 and len(results) == 4 * RESULTS_PER_PAGE


def test_call_cap_includes_retries():
    c, _ = client(FakeOpener([500, 500]), search_terms=["a"], max_calls=2, max_retries=5)
    assert list(c.fetch()) == []
    assert c.calls == 2 and "budget" in c.errors[0]


def test_max_pages_is_capped_at_five():
    c, _ = client(FakeOpener([]), max_pages=50)
    assert c.max_pages == 5


def test_to_job_maps_adzuna_fields():
    job = to_job(
        {
            "id": 4321,
            "title": "Data Engineer",
            "company": {"display_name": "Takealot"},
            "location": {"display_name": "Cape Town, Western Cape", "area": ["South Africa", "Western Cape"]},
            "salary_min": 600000,
            "salary_max": "800000",
            "salary_is_predicted": "1",
            "contract_time": "full_time",
            "contract_type": "permanent",
            "created": "2026-10-01T10:00:00Z",
            "redirect_url": "https://adzuna.co.za/x",
            "description": "SQL",
            "category": {"label": "IT Jobs"},
        },
        "data engineer",
    )
    assert (job.source, job.source_id, job.salary_currency, job.salary_period) == ("adzuna", "4321", "ZAR", "year")
    assert job.salary_is_predicted is True and job.salary_max == 800000.0
    assert job.employment_type_raw == "full_time, permanent"
    assert job.category == "IT Jobs" and job.search_term == "data engineer"


def test_to_job_without_salary():
    job = to_job({"id": "1", "title": "X", "salary_min": "n/a"})
    assert (job.salary_min, job.salary_currency, job.salary_is_predicted) == (None, None, False)


def test_load_sample_rebases_dates():
    now = datetime(2027, 1, 15, 12, tzinfo=UTC)
    results = load_sample(now)
    assert 30 <= len(results) <= 40
    newest = max(parse_datetime(r["created"]) for r in results)
    assert newest == datetime(2027, 1, 15, 10, tzinfo=UTC)
    assert all({"id", "title", "description", "company", "location", "redirect_url"} <= set(r) for r in results)


def test_adzuna_error_is_runtime_error():
    assert issubclass(AdzunaError, RuntimeError)
