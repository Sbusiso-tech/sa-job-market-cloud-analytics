"""The ``Job`` record shared by ingestion, processing, the API and the alert matcher."""
from __future__ import annotations

import hashlib
from dataclasses import asdict, dataclass, field, fields
from datetime import UTC, datetime
from typing import Any

SCHEMA_VERSION = 1

PUBLIC_JOB_FIELDS = (
    "job_id",
    "title",
    "company",
    "location",
    "city",
    "province",
    "is_remote",
    "salary_min_zar",
    "salary_max_zar",
    "salary_is_predicted",
    "seniority",
    "employment_type",
    "experience_years_min",
    "experience_years_max",
    "skills",
    "date_posted",
    "url",
    "source",
    "description_snippet",
)


def utc_now() -> datetime:
    return datetime.now(UTC)


def utc_now_iso() -> str:
    return format_datetime(utc_now())


def format_datetime(value: datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def parse_datetime(value: Any) -> datetime | None:
    if value in (None, ""):
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=UTC)
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(value, tz=UTC)
    try:
        parsed = datetime.fromisoformat(str(value).strip().replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)


def normalize_datetime(value: Any) -> str | None:
    parsed = parse_datetime(value)
    return format_datetime(parsed) if parsed else None


def make_job_id(source: str, source_id: str) -> str:
    return hashlib.sha1(f"{source}:{source_id}".encode(), usedforsecurity=False).hexdigest()


@dataclass
class Job:
    """A job posting. Raw fields come from the source; enriched fields are filled by ``transform.enrich``."""

    source: str
    source_id: str
    title: str
    job_id: str = ""
    schema_version: int = SCHEMA_VERSION
    ingested_at: str = field(default_factory=utc_now_iso)
    search_term: str | None = None

    company: str | None = None
    location: str | None = None
    location_area: list[str] = field(default_factory=list)
    country: str | None = "ZA"
    category: str | None = None

    salary_text: str | None = None
    salary_min: float | None = None
    salary_max: float | None = None
    salary_currency: str | None = None
    salary_period: str | None = None
    salary_is_predicted: bool = False

    employment_type_raw: str | None = None
    experience_months: int | None = None
    description: str | None = None
    tags: list[str] = field(default_factory=list)
    date_posted: str | None = None
    url: str | None = None

    # Enriched
    skills: list[str] = field(default_factory=list)
    salary_min_zar: int | None = None
    salary_max_zar: int | None = None
    seniority: str | None = None
    employment_type: str | None = None
    experience_years_min: int | None = None
    experience_years_max: int | None = None
    province: str | None = None
    city: str | None = None
    is_remote: bool | None = None
    description_snippet: str | None = None

    def __post_init__(self) -> None:
        if not self.title or not str(self.title).strip():
            raise ValueError("title must not be blank")
        self.title = str(self.title).strip()
        self.source = str(self.source or "").strip()
        self.source_id = str(self.source_id if self.source_id is not None else "").strip()
        if not self.source or not self.source_id:
            raise ValueError("source and source_id are required")
        self.job_id = self.job_id or make_job_id(self.source, self.source_id)
        self.date_posted = normalize_datetime(self.date_posted)
        self.tags = [str(tag).strip() for tag in self.tags or [] if tag is not None and str(tag).strip()]
        self.location_area = [str(a).strip() for a in self.location_area or [] if a is not None and str(a).strip()]
        self.skills = list(self.skills or [])
        self.salary_is_predicted = bool(self.salary_is_predicted)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def to_public(self) -> dict[str, Any]:
        data = self.to_dict()
        return {name: data.get(name) for name in PUBLIC_JOB_FIELDS}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Job:
        known = {f.name for f in fields(cls)}
        return cls(**{key: value for key, value in data.items() if key in known})
