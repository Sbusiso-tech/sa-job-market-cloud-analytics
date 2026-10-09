from datetime import UTC, datetime, timedelta

from helpers import curated, make_job, sample_records
from sajobs.aggregate import (
    SECTIONS,
    compute_stats,
    dedupe_latest,
    empty_section,
    iso_week,
    percentile,
    salary_midpoint,
)
from sajobs.models import format_datetime

NOW = datetime(2026, 10, 9, 5, 0, tzinfo=UTC)


def record(job_id, skills, *, province="Gauteng", salary=None, seen=NOW, posted=None, **extra):
    return {
        "job_id": job_id,
        "skills": skills,
        "province": province,
        "salary_min_zar": salary,
        "salary_max_zar": salary,
        "seen_at": format_datetime(seen),
        "date_posted": format_datetime(posted or seen),
        "seniority": extra.get("seniority", "mid"),
        "employment_type": extra.get("employment_type", "full_time"),
    }


def test_percentile_and_midpoint():
    assert percentile([], 50) is None
    assert percentile([1, 2, 3, 4], 50) == 2.5
    assert percentile([10], 75) == 10
    assert percentile([100, 200, 300, 400, 500], 25) == 200
    assert salary_midpoint({"salary_min_zar": 100, "salary_max_zar": 200}) == 150
    assert salary_midpoint({"salary_min_zar": None, "salary_max_zar": 200}) == 200
    assert salary_midpoint({}) is None


def test_iso_week():
    assert iso_week(NOW) == "2026-W41"


def test_dedupe_keeps_latest():
    old = record("a", ["SQL"], seen=NOW - timedelta(days=2))
    new = record("a", ["SQL", "Python"], seen=NOW)
    assert dedupe_latest([new, old, {"job_id": None}]) == [new]


def test_compute_stats_shapes_match_contract():
    stats = compute_stats(sample_records(NOW), NOW)
    sections = stats["sections"]
    assert set(sections) == set(SECTIONS)
    overview = sections["OVERVIEW"]
    assert overview["total_jobs"] == 36 and overview["window_days"] == 30
    assert overview["top_skill"] == "SQL" and overview["top_province"] == "Gauteng"
    assert isinstance(overview["median_salary_zar"], int)
    assert {s["name"] for s in overview["seniority"]} <= {"intern", "junior", "mid", "senior", "lead", "unspecified"}
    assert sum(s["count"] for s in overview["employment_type"]) == 36
    skill = sections["SKILLS"]["skills"][0]
    assert set(skill) == {"skill", "category", "count", "share", "change_vs_prev_week"}
    assert len(sections["SKILLS"]["skills"]) <= 30
    salary = sections["SALARIES"]["salaries"][0]
    assert set(salary) == {"skill", "sample_size", "p25", "median", "p75"} and salary["sample_size"] >= 5
    assert salary["p25"] <= salary["median"] <= salary["p75"]
    province = sections["PROVINCES"]["provinces"][0]
    assert set(province) == {"province", "count", "median_salary_zar", "top_skills"}
    assert len(province["top_skills"]) <= 5
    counts = [p["count"] for p in sections["PROVINCES"]["provinces"]]
    assert counts == sorted(counts, reverse=True)
    pair = sections["PAIRS"]["pairs"][0]
    assert pair["skills"] == sorted(pair["skills"], key=str.lower) and len(sections["PAIRS"]["pairs"]) <= 20
    assert sections["TRENDS"]["weeks"] == [stats["snapshot"]]
    assert stats["snapshot"]["week"] == "2026-W41"
    for name in ("OVERVIEW", "SKILLS", "SALARIES", "PROVINCES", "PAIRS"):
        assert sections[name]["last_updated"] == "2026-10-09T05:00:00Z"


def test_window_weekly_change_and_salary_threshold():
    records = [
        record("old", ["SQL"], seen=NOW - timedelta(days=35)),  # outside the 30-day window
        *[record(f"t{i}", ["SQL", "Python"], salary=500_000 + i * 10_000) for i in range(5)],
        record("p1", ["SQL"], posted=NOW - timedelta(days=10), seen=NOW - timedelta(days=1)),
        record("p2", ["Python"], posted=NOW - timedelta(days=9), seen=NOW - timedelta(days=9), province="Unknown"),
    ]
    sections = compute_stats(records, NOW)["sections"]
    assert sections["OVERVIEW"]["total_jobs"] == 7
    assert sections["OVERVIEW"]["new_this_week"] == 5
    skills = {s["skill"]: s for s in sections["SKILLS"]["skills"]}
    assert skills["SQL"]["count"] == 6 and skills["SQL"]["share"] == round(6 / 7, 3)
    # posted this week: 5 SQL / 5 Python; posted the week before: p1 (SQL) and p2 (Python)
    assert skills["SQL"]["change_vs_prev_week"] == 4
    assert skills["Python"]["change_vs_prev_week"] == 4
    salaries = {s["skill"]: s for s in sections["SALARIES"]["salaries"]}
    assert salaries["SQL"] == {"skill": "SQL", "sample_size": 5, "p25": 510_000, "median": 520_000, "p75": 530_000}
    provinces = sections["PROVINCES"]["provinces"]
    assert provinces[-1]["province"] == "Unknown" and provinces[-1]["median_salary_zar"] is None
    assert sections["OVERVIEW"]["top_province"] == "Gauteng"
    # snapshot counts only jobs seen in the last 7 days
    assert compute_stats(records, NOW)["snapshot"]["total_jobs"] == 6


def test_trends_merge_keeps_last_twelve_weeks_oldest_first():
    previous = [{"week": f"2026-W{w:02d}", "total_jobs": w, "top_skills": []} for w in range(25, 41)]
    previous.append({"week": "2026-W41", "total_jobs": 999, "top_skills": []})
    weeks = compute_stats([record("a", ["SQL"])], NOW, previous)["sections"]["TRENDS"]["weeks"]
    assert len(weeks) == 12
    assert weeks[0]["week"] == "2026-W30" and weeks[-1]["week"] == "2026-W41"
    assert weeks[-1]["total_jobs"] == 1


def test_empty_input_and_empty_sections():
    sections = compute_stats([], NOW)["sections"]
    assert sections["OVERVIEW"]["total_jobs"] == 0 and sections["OVERVIEW"]["top_skill"] is None
    assert sections["SKILLS"]["skills"] == []
    for name in SECTIONS:
        empty = empty_section(name)
        assert set(empty) == set(sections[name])


def test_unknown_values_fall_back():
    rec = curated(make_job(), NOW)
    rec["seniority"] = None
    rec["employment_type"] = "weird"
    overview = compute_stats([rec], NOW)["sections"]["OVERVIEW"]
    assert overview["seniority"] == [{"name": "unspecified", "count": 1}]
    assert overview["employment_type"] == [{"name": "weird", "count": 1}]
