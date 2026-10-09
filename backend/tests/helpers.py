"""Shared builders for tests."""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from sajobs.adzuna import load_sample, to_job
from sajobs.models import Job, format_datetime
from sajobs.repository import Repository
from sajobs.transform import enrich


def make_job(**overrides: Any) -> Job:
    data = {
        "source": "adzuna",
        "source_id": "1",
        "title": "Senior Data Engineer",
        "company": "Acme Bank",
        "location": "Sandton, Johannesburg",
        "location_area": ["South Africa", "Gauteng", "Johannesburg", "Sandton"],
        "salary_min": 600000.0,
        "salary_max": 780000.0,
        "salary_currency": "ZAR",
        "salary_period": "year",
        "employment_type_raw": "full_time, permanent",
        "description": "<p>5+ years of Python, SQL and AWS.</p>",
        "date_posted": "2026-10-07T09:00:00Z",
        "url": "https://www.adzuna.co.za/details/1",
    }
    data.update(overrides)
    return Job(**data)


def curated(job: Job, seen_at: datetime) -> dict[str, Any]:
    return {**enrich(job).to_dict(), "seen_at": format_datetime(seen_at)}


def sample_records(now: datetime) -> list[dict[str, Any]]:
    return [curated(to_job(raw), now) for raw in load_sample(now)]


def seed_jobs(table, now: datetime, jobs: list[dict[str, Any]] | None = None) -> list[dict[str, Any]]:
    repo = Repository(table)
    records = jobs if jobs is not None else sample_records(now)
    for i, record in enumerate(records):
        record = dict(record)
        record["date_posted"] = format_datetime(now - timedelta(hours=i))
        repo.put_job_if_new(Repository.job_item(record, now))
    return records
