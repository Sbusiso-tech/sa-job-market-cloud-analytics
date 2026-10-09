"""Adzuna South Africa search API client (https://developer.adzuna.com), standard library only.

Free keys allow 25 calls/minute and 250/day, so the client paces calls, retries 429/5xx with backoff and
stops at a hard cap of ``max_calls`` HTTP requests per run (retries included).
"""
from __future__ import annotations

import json
import logging
import time
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable, Iterator
from datetime import UTC, datetime, timedelta
from importlib import resources
from typing import Any

from sajobs.models import Job, format_datetime, parse_datetime

log = logging.getLogger(__name__)

API_URL = "https://api.adzuna.com/v1/api/jobs/za/search/{page}"
SOURCE = "adzuna"
RESULTS_PER_PAGE = 50
DEFAULT_SEARCH_TERMS = (
    "software developer",
    "data engineer",
    "data analyst",
    "cloud engineer",
    "devops",
    "cyber security",
    "business analyst",
    "IT support",
)
USER_AGENT = "sa-jobmarket/1.0 (portfolio project)"
RETRY_STATUSES = {429, 500, 502, 503, 504}

Opener = Callable[..., Any]


class AdzunaError(RuntimeError):
    pass


class AdzunaClient:
    def __init__(
        self,
        app_id: str,
        app_key: str,
        *,
        opener: Opener | None = None,
        sleep: Callable[[float], None] = time.sleep,
        clock: Callable[[], float] = time.monotonic,
        search_terms: tuple[str, ...] | list[str] = DEFAULT_SEARCH_TERMS,
        max_pages: int = 5,
        max_calls: int = 40,
        calls_per_minute: int = 25,
        max_retries: int = 3,
        max_days_old: int = 30,
        timeout: float = 20.0,
    ):
        self.app_id = app_id
        self.app_key = app_key
        self.opener = opener or urllib.request.urlopen
        self.sleep = sleep
        self.clock = clock
        self.search_terms = tuple(search_terms)
        self.max_pages = max(1, min(max_pages, 5))
        self.max_calls = max_calls
        self.min_interval = 60.0 / calls_per_minute
        self.max_retries = max_retries
        self.max_days_old = max_days_old
        self.timeout = timeout
        self.calls = 0
        self.errors: list[str] = []
        self._last_call: float | None = None

    # ------------------------------------------------------------------ HTTP

    def _pace(self) -> None:
        if self._last_call is not None:
            wait = self.min_interval - (self.clock() - self._last_call)
            if wait > 0:
                self.sleep(wait)
        self._last_call = self.clock()

    def _request(self, page: int, term: str) -> dict[str, Any]:
        query = urllib.parse.urlencode(
            {
                "app_id": self.app_id,
                "app_key": self.app_key,
                "results_per_page": RESULTS_PER_PAGE,
                "what": term,
                "max_days_old": self.max_days_old,
                "sort_by": "date",
                "content-type": "application/json",
            }
        )
        url = API_URL.format(page=page) + "?" + query
        headers = {"User-Agent": USER_AGENT, "Accept": "application/json"}
        request = urllib.request.Request(url, headers=headers)  # noqa: S310 - fixed https URL
        attempt = 0
        while True:
            if self.calls >= self.max_calls:
                raise AdzunaError(f"call budget of {self.max_calls} exhausted")
            self._pace()
            self.calls += 1
            try:
                with self.opener(request, timeout=self.timeout) as response:
                    return json.loads(response.read().decode("utf-8"))
            except urllib.error.HTTPError as exc:
                retryable = exc.code in RETRY_STATUSES
                detail = f"HTTP {exc.code}"
                retry_after = _retry_after(exc)
            except (urllib.error.URLError, TimeoutError, ConnectionError) as exc:
                retryable = True
                detail = type(exc).__name__
                retry_after = None
            except json.JSONDecodeError as exc:
                raise AdzunaError(f"invalid JSON for term={term!r} page={page}") from exc
            # Never log the URL: it carries the app key.
            log.warning("adzuna term=%r page=%d attempt=%d failed: %s", term, page, attempt + 1, detail)
            if not retryable or attempt >= self.max_retries:
                raise AdzunaError(f"term={term!r} page={page}: {detail}")
            self.sleep(retry_after if retry_after is not None else min(30.0, 2.0 * 2**attempt))
            attempt += 1

    # ------------------------------------------------------------------ API

    def fetch(self) -> Iterator[tuple[dict[str, Any], str]]:
        """Yield ``(raw_result, search_term)`` for every distinct job across all search terms."""
        seen: set[str] = set()
        for term in self.search_terms:
            for page in range(1, self.max_pages + 1):
                if self.calls >= self.max_calls:
                    log.warning("adzuna call cap %d reached; stopping", self.max_calls)
                    return
                try:
                    payload = self._request(page, term)
                except AdzunaError as exc:
                    self.errors.append(str(exc))
                    break
                results = payload.get("results") or []
                log.info("adzuna term=%r page=%d jobs=%d", term, page, len(results))
                for raw in results:
                    source_id = str(raw.get("id") or "")
                    if source_id and source_id not in seen:
                        seen.add(source_id)
                        yield raw, term
                if len(results) < RESULTS_PER_PAGE:
                    break


def _retry_after(exc: urllib.error.HTTPError) -> float | None:
    value = exc.headers.get("Retry-After") if exc.headers else None
    try:
        return min(30.0, max(0.0, float(value))) if value is not None else None
    except ValueError:
        return None


def to_job(raw: dict[str, Any], search_term: str | None = None) -> Job:
    """Map one Adzuna result onto a :class:`Job` (salaries from Adzuna ZA are annual rand)."""
    employment = [v for v in (raw.get("contract_time"), raw.get("contract_type")) if v]
    location = raw.get("location") or {}
    salary_min, salary_max = _number(raw.get("salary_min")), _number(raw.get("salary_max"))
    has_salary = bool(salary_min or salary_max)
    category = (raw.get("category") or {}).get("label")
    return Job(
        source=SOURCE,
        source_id=str(raw["id"]),
        title=raw.get("title") or "",
        search_term=search_term,
        company=(raw.get("company") or {}).get("display_name"),
        location=location.get("display_name"),
        location_area=list(location.get("area") or []),
        country="ZA",
        category=category,
        salary_min=salary_min,
        salary_max=salary_max,
        salary_currency="ZAR" if has_salary else None,
        salary_period="year" if has_salary else None,
        salary_is_predicted=str(raw.get("salary_is_predicted", "0")) == "1",
        employment_type_raw=", ".join(employment) or None,
        description=(raw.get("description") or "")[:20_000],
        date_posted=raw.get("created"),
        url=raw.get("redirect_url"),
    )


def _number(value: Any) -> float | None:
    try:
        return float(value) if value not in (None, "") else None
    except (TypeError, ValueError):
        return None


def load_sample(now: datetime | None = None) -> list[dict[str, Any]]:
    """Bundled fake Adzuna results, with ``created`` dates shifted so the newest is ``now`` minus 2 hours."""
    raw = json.loads(resources.files("sajobs").joinpath("sample_data/adzuna_za_sample.json").read_text("utf-8"))
    results = raw["results"]
    created = [parse_datetime(r.get("created")) for r in results]
    newest = max((c for c in created if c), default=None)
    if newest is None:
        return results
    shift = ((now or datetime.now(UTC)) - timedelta(hours=2)) - newest
    shifted = []
    for result, when in zip(results, created, strict=True):
        item = dict(result)
        if when:
            item["created"] = format_datetime(when + shift)
        shifted.append(item)
    return shifted
