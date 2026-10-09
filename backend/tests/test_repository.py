from datetime import UTC, datetime
from decimal import Decimal

import pytest

from helpers import curated, make_job
from sajobs.repository import Repository, decode_cursor, encode_cursor, from_dynamo, public_job, to_dynamo

NOW = datetime(2026, 10, 9, 5, 0, tzinfo=UTC)


def test_decimal_conversion_round_trip():
    value = {"a": 1.5, "b": [2.0, True, None], "c": {"d": 3}}
    stored = to_dynamo(value)
    assert stored["a"] == Decimal("1.5") and stored["b"][1] is True
    assert from_dynamo(stored) == {"a": 1.5, "b": [2, True, None], "c": {"d": 3}}
    assert from_dynamo({"s": {"b", "a"}}) == {"s": ["a", "b"]}


def test_cursor_round_trip_and_validation():
    key = {"PK": "JOB#1", "SK": "META", "GSI2PK": "JOBS", "GSI2SK": "2026#1"}
    cursor = encode_cursor(key)
    assert "=" not in cursor
    assert decode_cursor(cursor, set(key)) == key
    assert encode_cursor(None) is None and decode_cursor(None, set()) is None
    for bad in ("!!!", "bm90IGpzb24", encode_cursor({"PK": "x"})):
        with pytest.raises(ValueError):
            decode_cursor(bad, set(key))


def test_job_item_keys_and_ttl():
    item = Repository.job_item(curated(make_job(), NOW), NOW)
    assert item["PK"].startswith("JOB#") and item["SK"] == "META"
    assert item["GSI1PK"] == "PROV#Gauteng"
    assert item["GSI2PK"] == "JOBS"
    assert item["GSI1SK"] == item["GSI2SK"] == f"2026-10-07T09:00:00Z#{item['job_id']}"
    assert item["ttl"] == int(NOW.timestamp()) + 60 * 86400
    assert "description" not in item and len(item["description_snippet"]) <= 300


def test_public_job_defaults():
    job = public_job({"job_id": "x", "skills": None, "is_remote": None, "salary_min_zar": Decimal("100")})
    assert job["skills"] == [] and job["is_remote"] is False and job["salary_min_zar"] == 100


def test_put_if_new_touch_and_counts(cloud):
    repo = Repository(cloud.table)
    item = Repository.job_item(curated(make_job(), NOW), NOW)
    assert repo.put_job_if_new(item) is True
    assert repo.put_job_if_new(item) is False
    later = datetime(2026, 11, 1, tzinfo=UTC)
    relocated = {**item, "province": "Western Cape", "GSI1PK": "PROV#Western Cape", "city": None, "is_remote": True}
    repo.touch_job(relocated, later)
    stored = cloud.table.get_item(Key={"PK": item["PK"], "SK": "META"})["Item"]
    assert stored["ttl"] == int(later.timestamp()) + 60 * 86400
    assert (stored["province"], stored["GSI1PK"], stored["city"], stored["is_remote"]) == (
        "Western Cape", "PROV#Western Cape", None, True
    )
    assert stored["first_seen"] == item["first_seen"]

    repo.start_run("run-1", fetched=5, source="sample", started_at="2026-10-09T05:00:00Z")
    repo.add_run_counts("run-1", new_jobs=2)
    repo.add_run_counts("run-1", failed=1)
    repo.add_run_counts("run-1")
    run = repo.finish_run("run-1", "SUCCEEDED", datetime(2026, 10, 9, 5, 2, tzinfo=UTC), error="x" * 2000)
    assert (run["fetched"], run["new_jobs"], run["failed"], run["duration_seconds"]) == (5, 2, 1, 120)
    assert len(run["error"]) == 1000
    assert repo.finish_run("missing", "FAILED", NOW)["status"] == "FAILED"
    assert repo.get_run("nope") is None


def test_put_if_new_reraises_other_errors(cloud):
    repo = Repository(cloud.table)
    with pytest.raises(Exception):  # noqa: B017 - moto raises a ValidationException ClientError
        repo.put_job_if_new({"PK": "JOB#x"})


def test_user_profile_alerts_and_delete(cloud):
    repo = Repository(cloud.table)
    with pytest.raises(ValueError):
        repo.get_profile("")
    repo.put_profile("u1", "a@example.com", "arn:1", NOW)
    repo.put_profile("u1", "a@example.com", None, datetime(2027, 1, 1, tzinfo=UTC))
    assert repo.get_profile("u1")["created_at"] == "2026-10-09T05:00:00Z"
    repo.create_alert("u1", "al1", ["Python", "SQL"], "Gauteng", NOW)
    assert [a["sub"] for a in repo.alerts_for_skill("Python")] == ["u1"]
    assert repo.delete_alert("u1", "missing") is False
    assert repo.delete_user("u1") == 4
    assert repo.alerts_for_skill("Python") == []
    assert repo.get_profile("u1") is None
