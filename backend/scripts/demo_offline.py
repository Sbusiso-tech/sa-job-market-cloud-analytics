"""Offline demo: enrich the bundled sample Adzuna data and print SA top skills, provinces and salaries.

Run with ``make demo`` (no AWS account or Adzuna key needed).
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from sajobs.adzuna import load_sample, to_job  # noqa: E402
from sajobs.aggregate import compute_stats  # noqa: E402
from sajobs.models import format_datetime, utc_now  # noqa: E402
from sajobs.transform import enrich  # noqa: E402


def rand(value: int | None) -> str:
    return "-" if value is None else "R" + f"{value:,}".replace(",", " ")


def main() -> None:
    now = utc_now()
    records = []
    for raw in load_sample(now):
        job = enrich(to_job(raw))
        records.append({**job.to_dict(), "seen_at": format_datetime(now)})
    sections = compute_stats(records, now)["sections"]
    overview = sections["OVERVIEW"]

    print(f"SA job market (sample data): {overview['total_jobs']} jobs, {overview['new_this_week']} new this week")
    print(f"Median salary {rand(overview['median_salary_zar'])} per year | top skill {overview['top_skill']} "
          f"| top province {overview['top_province']}\n")

    print("Top 10 skills")
    for row in sections["SKILLS"]["skills"][:10]:
        print(f"  {row['skill']:<22} {row['count']:>3}  {row['share']:>6.1%}  ({row['category']})")

    print("\nJobs per province")
    for row in sections["PROVINCES"]["provinces"]:
        top = ", ".join(s["skill"] for s in row["top_skills"][:3])
        print(f"  {row['province']:<15} {row['count']:>3}  median {rand(row['median_salary_zar']):>12}  top: {top}")

    print("\nSalaries (ZAR per year, skills with >= 5 salaried jobs)")
    print(f"  {'skill':<22} {'n':>3} {'p25':>12} {'median':>12} {'p75':>12}")
    for row in sections["SALARIES"]["salaries"]:
        print(f"  {row['skill']:<22} {row['sample_size']:>3} {rand(row['p25']):>12} {rand(row['median']):>12} "
              f"{rand(row['p75']):>12}")

    print("\nTop skill pairs")
    for row in sections["PAIRS"]["pairs"][:5]:
        print(f"  {' + '.join(row['skills']):<30} {row['count']:>3}")


if __name__ == "__main__":
    main()
