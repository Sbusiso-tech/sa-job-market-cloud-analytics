"""Pure functions that turn curated job records into the public statistics in ``docs/api-contract.md``.

A curated record is an enriched job dict with at least ``job_id``, ``seen_at`` (when the pipeline last saw it),
``date_posted``, ``province``, ``skills``, ``salary_min_zar``/``salary_max_zar``, ``seniority`` and
``employment_type``.
"""
from __future__ import annotations

from collections import Counter
from collections.abc import Iterable
from datetime import datetime, timedelta
from itertools import combinations
from typing import Any

from sajobs.models import format_datetime, parse_datetime
from sajobs.provinces import UNKNOWN
from sajobs.skills import skill_categories
from sajobs.transform import EMPLOYMENT_TYPES, SENIORITY_LEVELS

WINDOW_DAYS = 30
TOP_SKILLS = 30
TOP_PAIRS = 20
TOP_PROVINCE_SKILLS = 5
TREND_SKILLS = 10
MAX_TREND_WEEKS = 12
MIN_SALARY_SAMPLE = 5

SECTIONS = ("OVERVIEW", "SKILLS", "SALARIES", "PROVINCES", "PAIRS", "TRENDS")


def iso_week(when: datetime) -> str:
    year, week, _ = when.isocalendar()
    return f"{year}-W{week:02d}"


def percentile(values: list[float], pct: float) -> float | None:
    """Linear-interpolated percentile (same as numpy's default), ``pct`` in 0..100."""
    if not values:
        return None
    ordered = sorted(values)
    rank = (len(ordered) - 1) * pct / 100
    low = int(rank)
    high = min(low + 1, len(ordered) - 1)
    return ordered[low] + (ordered[high] - ordered[low]) * (rank - low)


def _round(value: float | None) -> int | None:
    return None if value is None else int(round(value))


def salary_midpoint(record: dict[str, Any]) -> float | None:
    low, high = record.get("salary_min_zar"), record.get("salary_max_zar")
    if low is None and high is None:
        return None
    low = high if low is None else low
    high = low if high is None else high
    return (float(low) + float(high)) / 2


def _seen(record: dict[str, Any]) -> datetime | None:
    return parse_datetime(record.get("seen_at")) or parse_datetime(record.get("ingested_at"))


def _posted(record: dict[str, Any]) -> datetime | None:
    return parse_datetime(record.get("date_posted")) or _seen(record)


def dedupe_latest(records: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    """Keep one record per ``job_id``: the one seen most recently."""
    latest: dict[str, dict[str, Any]] = {}
    for record in records:
        job_id = record.get("job_id")
        if not job_id:
            continue
        current = latest.get(job_id)
        if current is None or (record.get("seen_at") or "") >= (current.get("seen_at") or ""):
            latest[job_id] = record
    return list(latest.values())


def _skill_counts(records: Iterable[dict[str, Any]]) -> Counter:
    counts: Counter = Counter()
    for record in records:
        counts.update(set(record.get("skills") or []))
    return counts


def _ranked(counts: Counter, limit: int) -> list[tuple[str, int]]:
    return sorted(counts.items(), key=lambda kv: (-kv[1], kv[0].lower()))[:limit]


def _breakdown(records: list[dict[str, Any]], key: str, order: tuple[str, ...]) -> list[dict[str, Any]]:
    counts = Counter(record.get(key) or "unspecified" for record in records)
    names = [name for name in order if counts.get(name)] + sorted(n for n in counts if n not in order)
    return [{"name": name, "count": counts[name]} for name in names]


def _median_salary(records: Iterable[dict[str, Any]]) -> int | None:
    values = [v for v in (salary_midpoint(r) for r in records) if v is not None]
    return _round(percentile(values, 50)) if len(values) >= MIN_SALARY_SAMPLE else None


def _top_skills(records: Iterable[dict[str, Any]], limit: int) -> list[dict[str, Any]]:
    return [{"skill": name, "count": count} for name, count in _ranked(_skill_counts(records), limit)]


def compute_stats(
    records: Iterable[dict[str, Any]],
    now: datetime,
    previous_weeks: list[dict[str, Any]] | None = None,
    window_days: int = WINDOW_DAYS,
) -> dict[str, Any]:
    """Return ``{"sections": {OVERVIEW..TRENDS}, "week": "yyyy-Www", "snapshot": {...}}``."""
    updated = format_datetime(now)
    jobs = dedupe_latest(records)
    window_start = now - timedelta(days=window_days)
    window = [r for r in jobs if (_seen(r) or now) >= window_start]
    total = len(window)
    week_ago, two_weeks_ago = now - timedelta(days=7), now - timedelta(days=14)
    this_week = [r for r in jobs if (_posted(r) or now) > week_ago]
    prev_week = [r for r in jobs if two_weeks_ago < (_posted(r) or now) <= week_ago]

    categories = skill_categories()
    skill_counts = _skill_counts(window)
    this_counts, prev_counts = _skill_counts(this_week), _skill_counts(prev_week)
    ranked_skills = _ranked(skill_counts, TOP_SKILLS)
    skills = [
        {
            "skill": name,
            "category": categories.get(name, "Other"),
            "count": count,
            "share": round(count / total, 3) if total else 0.0,
            "change_vs_prev_week": this_counts.get(name, 0) - prev_counts.get(name, 0),
        }
        for name, count in ranked_skills
    ]

    by_province: dict[str, list[dict[str, Any]]] = {}
    for record in window:
        by_province.setdefault(record.get("province") or UNKNOWN, []).append(record)
    provinces = sorted(
        (
            {
                "province": province,
                "count": len(items),
                "median_salary_zar": _median_salary(items),
                "top_skills": _top_skills(items, TOP_PROVINCE_SKILLS),
            }
            for province, items in by_province.items()
        ),
        key=lambda p: (-p["count"], p["province"]),
    )
    top_province = next((p["province"] for p in provinces if p["province"] != UNKNOWN), None)

    salaries_by_skill: dict[str, list[float]] = {}
    for record in window:
        mid = salary_midpoint(record)
        if mid is None:
            continue
        for skill in set(record.get("skills") or []):
            salaries_by_skill.setdefault(skill, []).append(mid)
    salaries = sorted(
        (
            {
                "skill": skill,
                "sample_size": len(values),
                "p25": _round(percentile(values, 25)),
                "median": _round(percentile(values, 50)),
                "p75": _round(percentile(values, 75)),
            }
            for skill, values in salaries_by_skill.items()
            if len(values) >= MIN_SALARY_SAMPLE
        ),
        key=lambda s: (-s["median"], s["skill"].lower()),
    )

    pair_counts: Counter = Counter()
    for record in window:
        names = sorted(set(record.get("skills") or []), key=str.lower)
        pair_counts.update(combinations(names, 2))
    pairs = [
        {"skills": list(pair), "count": count}
        for pair, count in sorted(pair_counts.items(), key=lambda kv: (-kv[1], kv[0][0].lower(), kv[0][1].lower()))[
            :TOP_PAIRS
        ]
    ]

    week = iso_week(now)
    seen_this_week = [r for r in window if (_seen(r) or now) > week_ago]
    snapshot = {
        "week": week,
        "total_jobs": len(seen_this_week),
        "top_skills": _top_skills(seen_this_week, TREND_SKILLS),
    }
    weeks = {w["week"]: w for w in (previous_weeks or []) if w.get("week")}
    weeks[week] = snapshot
    trend_weeks = [weeks[key] for key in sorted(weeks)][-MAX_TREND_WEEKS:]

    sections = {
        "OVERVIEW": {
            "last_updated": updated,
            "window_days": window_days,
            "total_jobs": total,
            "new_this_week": sum(1 for r in window if (_posted(r) or now) > week_ago),
            "median_salary_zar": _median_salary(window),
            "top_skill": ranked_skills[0][0] if ranked_skills else None,
            "top_province": top_province,
            "seniority": _breakdown(window, "seniority", SENIORITY_LEVELS),
            "employment_type": _breakdown(window, "employment_type", EMPLOYMENT_TYPES),
        },
        "SKILLS": {"last_updated": updated, "skills": skills},
        "SALARIES": {"last_updated": updated, "salaries": salaries},
        "PROVINCES": {"last_updated": updated, "provinces": provinces},
        "PAIRS": {"last_updated": updated, "pairs": pairs},
        "TRENDS": {"last_updated": updated, "weeks": trend_weeks},
    }
    return {"sections": sections, "week": week, "snapshot": snapshot}


def empty_section(name: str) -> dict[str, Any]:
    """The shape every public stats route returns before the first pipeline run."""
    return {
        "OVERVIEW": {
            "last_updated": None,
            "window_days": WINDOW_DAYS,
            "total_jobs": 0,
            "new_this_week": 0,
            "median_salary_zar": None,
            "top_skill": None,
            "top_province": None,
            "seniority": [],
            "employment_type": [],
        },
        "SKILLS": {"last_updated": None, "skills": []},
        "SALARIES": {"last_updated": None, "salaries": []},
        "PROVINCES": {"last_updated": None, "provinces": []},
        "PAIRS": {"last_updated": None, "pairs": []},
        "TRENDS": {"last_updated": None, "weeks": []},
    }[name]
