from datetime import UTC, datetime

import pytest

from helpers import make_job
from sajobs.models import Job, make_job_id, normalize_datetime, parse_datetime


def test_job_id_is_stable_sha1():
    job = make_job()
    assert job.job_id == make_job_id("adzuna", "1")
    assert len(job.job_id) == 40


def test_job_validation():
    with pytest.raises(ValueError):
        make_job(title="  ")
    with pytest.raises(ValueError):
        make_job(source_id="")


def test_round_trip_and_public_shape():
    job = make_job(tags=[" x ", None, ""], location_area=["South Africa", " "])
    again = Job.from_dict({**job.to_dict(), "unknown_field": 1})
    assert again == job
    assert job.tags == ["x"] and job.location_area == ["South Africa"]
    assert set(job.to_public()) >= {"job_id", "salary_min_zar", "description_snippet"}


def test_datetime_helpers():
    assert normalize_datetime("2026-10-07T09:00:00") == "2026-10-07T09:00:00Z"
    assert normalize_datetime("not a date") is None
    assert parse_datetime(0) == datetime(1970, 1, 1, tzinfo=UTC)
    assert parse_datetime(datetime(2026, 1, 1)).tzinfo is not None
    assert parse_datetime("") is None
