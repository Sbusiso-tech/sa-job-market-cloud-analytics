"""Pure-Python cleaning and enrichment rules (ported from the Job Market Intelligence Platform).

Salaries are reported in rand (ZAR) per year: hour x2080, day x260, week x52, month x12.
"""
from __future__ import annotations

import html
import re
from dataclasses import replace
from typing import Any

from sajobs.models import Job
from sajobs.provinces import resolve_location
from sajobs.skills import extract_skill_names

HOURS_PER_YEAR = 2080
PERIOD_MULTIPLIER = {"hour": HOURS_PER_YEAR, "day": 260, "week": 52, "month": 12, "year": 1}

EMPLOYMENT_TYPES = ("full_time", "part_time", "contract", "internship", "temporary", "unspecified")
SENIORITY_LEVELS = ("intern", "junior", "mid", "senior", "lead", "unspecified")

# Plausible annual ZAR range; anything outside is treated as a data error and dropped.
MIN_ANNUAL_ZAR = 12_000
MAX_ANNUAL_ZAR = 15_000_000
# An "annual" rand figure below this (about the national minimum wage for a year) is really a monthly salary.
MIN_FULL_TIME_ANNUAL = 60_000
SNIPPET_LENGTH = 300

# --------------------------------------------------------------------------- text

_BLOCK_TAGS = re.compile(r"</?(?:p|div|br|li|ul|ol|h[1-6]|tr|table|section)\b[^>]*>", re.IGNORECASE)
_ANY_TAG = re.compile(r"<[^>]+>")
_WS = re.compile(r"[ \t\r\f\v]+")
_BLANK_LINES = re.compile(r"\n\s*\n+")


def strip_html(value: str | None) -> str:
    if not value:
        return ""
    text = _BLOCK_TAGS.sub("\n", value)
    text = _ANY_TAG.sub(" ", text)
    text = html.unescape(text).replace("\xa0", " ")
    text = "\n".join(line.strip() for line in _WS.sub(" ", text).split("\n"))
    return _BLANK_LINES.sub("\n", text).strip()


def snippet(text: str | None, length: int = SNIPPET_LENGTH) -> str | None:
    if not text:
        return None
    flat = re.sub(r"\s+", " ", text).strip()
    if len(flat) <= length:
        return flat
    cut = flat[: length - 1].rsplit(" ", 1)[0].rstrip(" ,.;:")
    return cut + "…"


# ------------------------------------------------------------------------- salary

_CURRENCY_SYMBOLS = [
    ("US$", "USD"), ("A$", "AUD"), ("C$", "CAD"), ("$", "USD"), ("€", "EUR"), ("£", "GBP"),
    ("₹", "INR"), ("ZAR", "ZAR"), ("USD", "USD"), ("EUR", "EUR"), ("GBP", "GBP"), ("CAD", "CAD"),
    ("AUD", "AUD"), ("CHF", "CHF"), ("INR", "INR"),
]
_RAND = re.compile(r"(?<![A-Za-z])R\s?\d")
_NUMBER = re.compile(r"(\d+(?:[.,\s]\d+)*)\s*([kKmM])?(?![A-Za-z])")
_PERIODS = [
    ("hour", re.compile(r"/\s*h(?:ou)?r|per\s+hour|hourly|an?\s+hour|/hour|\bp\.?h\b", re.I)),
    ("day", re.compile(r"/\s*day|per\s+day|daily", re.I)),
    ("week", re.compile(r"/\s*w(?:ee)?k|per\s+week|weekly", re.I)),
    ("month", re.compile(r"/\s*mo(?:nth)?|per\s+month|monthly|\bp\.?\s?m\.?(?![a-z])", re.I)),
    ("year", re.compile(r"/\s*y(?:ea)?r|per\s+(?:year|annum)|annual|yearly|\bp\.?\s?a\.?(?![a-z])", re.I)),
]
# A rand amount (or range) in free text, e.g. "R35 000 per month", "R450k p.a.", "R 25,000 - R 30,000 pm CTC".
_RAND_AMOUNT = r"\d(?:[\d,.]|\s(?=\d))*\s*[kKmM]?(?![A-Za-z\d])"
_RAND_SALARY = re.compile(
    rf"(?<![A-Za-z])R\s?{_RAND_AMOUNT}"
    rf"(?:\s*(?:-|–|to)\s*R?\s?{_RAND_AMOUNT})?"
    r"(?i:[ \t]*(?:per\s+(?:hour|day|week|month|annum|year)|p\.?\s?[ahm]\.?(?![a-z])|monthly|annually|hourly|"
    r"daily|weekly|/\s*(?:hr|hour|day|week|month|mo|year|yr|annum)|ctc|cost to company))*"
)


def _parse_number(raw: str, suffix: str | None) -> float | None:
    raw = raw.strip().replace(" ", "")
    if suffix and re.fullmatch(r"\d+,\d{1,2}", raw):
        raw = raw.replace(",", ".")  # "35,3k" -> 35.3k (decimal comma)
    elif re.fullmatch(r"\d{1,3}(?:\.\d{3})+", raw):
        raw = raw.replace(".", "")  # "60.000" -> 60000 (thousands dot)
    elif re.fullmatch(r"[\d,]*,\d{2}", raw):
        raw = raw[:-3].replace(",", "") + "." + raw[-2:]  # "25 000,00" -> 25000.00 (SA decimal comma)
    else:
        raw = raw.replace(",", "")
    try:
        value = float(raw)
    except ValueError:
        return None
    if suffix in ("k", "K"):
        value *= 1_000
    elif suffix in ("m", "M"):
        value *= 1_000_000
    return value


def guess_period(amount: float, currency: str | None) -> str:
    """Pick a pay period for an amount stated without one (CTC figures included)."""
    if currency == "ZAR":
        return "hour" if amount < 1_000 else "month" if amount < 200_000 else "year"
    return "hour" if amount < 500 else "month" if amount < 20_000 else "year"


def parse_salary_text(text: str | None, default_currency: str | None = None) -> dict[str, Any]:
    """Parse free-text salaries such as ``"$90k - $105k"``, ``"R35 000 per month"`` or ``"R450k p.a."``."""
    empty = {"salary_min": None, "salary_max": None, "salary_currency": None, "salary_period": None}
    if not text or not re.search(r"\d", text):
        return empty

    currency = next((code for symbol, code in _CURRENCY_SYMBOLS if symbol in text), None)
    if currency is None and _RAND.search(text):
        currency = "ZAR"
    currency = currency or default_currency

    values = [v for v in (_parse_number(n, s) for n, s in _NUMBER.findall(text)) if v and v > 0][:2]
    if not values:
        return empty
    if len(values) == 2 and min(values) < max(values) / 50:
        values = [max(values)]  # a stray small number ("12 months") next to the real amount

    low, high = min(values), max(values)
    period = next((name for name, pattern in _PERIODS if pattern.search(text)), None) or guess_period(high, currency)
    return {"salary_min": low, "salary_max": high, "salary_currency": currency, "salary_period": period}


def find_rand_salary(text: str | None) -> str | None:
    """Return the first rand amount/range mentioned in a description, e.g. ``"R35 000 - R40 000 pm"``."""
    if not text:
        return None
    match = _RAND_SALARY.search(text)
    return match.group(0).strip() if match else None


_PERIOD_ALIASES = {
    "hour": "hour", "hourly": "hour", "hr": "hour",
    "day": "day", "daily": "day",
    "week": "week", "weekly": "week",
    "month": "month", "monthly": "month",
    "year": "year", "yearly": "year", "annual": "year", "annually": "year", "annum": "year",
}


def normalize_period(period: str | None) -> str | None:
    if not period:
        return None
    return _PERIOD_ALIASES.get(period.strip().lower())


def annualize(value: float | None, period: str | None) -> float | None:
    if value is None:
        return None
    return round(value * PERIOD_MULTIPLIER.get(period or "year", 1), 2)


def to_annual_zar(value: float | None, period: str | None, currency: str | None) -> int | None:
    """Annual rand value rounded to whole rands, or ``None`` when not rand or implausible."""
    if value is None or (currency not in (None, "ZAR")):
        return None
    annual = annualize(value, period)
    if annual is None or not MIN_ANNUAL_ZAR <= annual <= MAX_ANNUAL_ZAR:
        return None
    return int(round(annual))


# ----------------------------------------------------------------- employment type

_EMPLOYMENT_RULES = [
    ("internship", re.compile(r"intern|learnership|trainee|graduate programme|graduate program|in-service", re.I)),
    ("contract", re.compile(r"contract|freelance|contractor|fixed[\s-]term", re.I)),
    ("temporary", re.compile(r"temp|seasonal|locum", re.I)),
    ("part_time", re.compile(r"part[\s_-]?time", re.I)),
    ("full_time", re.compile(r"full[\s_-]?time|permanent|fulltime", re.I)),
]


def normalize_employment_type(raw: str | None, title: str | None = None) -> str:
    for candidate in (raw, title):
        if not candidate:
            continue
        for label, pattern in _EMPLOYMENT_RULES:
            if pattern.search(candidate):
                return label
    return "unspecified"


# ---------------------------------------------------------------------- experience

_YEARS = r"(?:years?|yrs?)"
_EXPERIENCE_PATTERNS = [
    re.compile(rf"(\d{{1,2}})\s*\+?\s*(?:-|–|to)\s*(\d{{1,2}})\s*\+?\s*{_YEARS}", re.I),
    re.compile(rf"(?:at least|minimum(?: of)?|min\.?|over|more than)\s*(\d{{1,2}})\s*\+?\s*{_YEARS}", re.I),
    re.compile(rf"(\d{{1,2}})\s*\+\s*{_YEARS}", re.I),
    re.compile(rf"(\d{{1,2}})\s*{_YEARS}(?:['’]s?)?\s+(?:of\s+)?(?:\w+\s+){{0,3}}experience", re.I),
]


def extract_experience(text: str | None, months: int | None = None) -> tuple[int | None, int | None]:
    if months:
        years = round(months / 12)
        return years, years
    if not text:
        return None, None
    mins: list[int] = []
    maxes: list[int] = []
    for pattern in _EXPERIENCE_PATTERNS:
        for match in pattern.finditer(text):
            numbers = [int(g) for g in match.groups() if g is not None]
            if not numbers or max(numbers) > 30:
                continue
            mins.append(min(numbers))
            maxes.append(max(numbers))
    if not mins:
        return None, None
    return min(mins), max(maxes)


_SENIORITY_RULES = [
    ("intern", re.compile(r"\b(?:intern|internship|learnership|in-service trainee)\b", re.I)),
    ("lead", re.compile(r"\b(?:lead|principal|staff|head of|director|architect|vp)\b", re.I)),
    ("senior", re.compile(r"\b(?:senior|sr\.?|snr)\b", re.I)),
    ("junior", re.compile(r"\b(?:junior|jr\.?|jnr|graduate|entry[\s-]level|associate)\b", re.I)),
    ("mid", re.compile(r"\b(?:mid[\s-]?level|intermediate|medior|mid)\b", re.I)),
]


def infer_seniority(title: str | None, experience_min: int | None, employment_raw: str | None = None) -> str:
    for candidate in (title, employment_raw):
        if not candidate:
            continue
        for label, pattern in _SENIORITY_RULES:
            if pattern.search(candidate):
                return label
    if experience_min is None:
        return "unspecified"
    if experience_min < 2:
        return "junior"
    if experience_min < 5:
        return "mid"
    return "senior"


# ------------------------------------------------------------------------- record


def _salary(job: Job, description: str) -> tuple[dict[str, Any], bool]:
    salary = {
        "salary_min": job.salary_min or None,
        "salary_max": job.salary_max or None,
        "salary_currency": job.salary_currency,
        "salary_period": normalize_period(job.salary_period),
    }
    predicted = job.salary_is_predicted
    if salary["salary_min"] is None and salary["salary_max"] is None:
        default_currency = "ZAR" if (job.country or "").upper() == "ZA" else None
        salary = parse_salary_text(job.salary_text or find_rand_salary(description), default_currency)
        predicted = False
    if salary["salary_min"] is not None or salary["salary_max"] is not None:
        high = salary["salary_max"] or salary["salary_min"]
        if salary["salary_period"] is None:
            salary["salary_period"] = guess_period(high, salary["salary_currency"])
        elif salary["salary_period"] == "year" and salary["salary_currency"] == "ZAR" and high < MIN_FULL_TIME_ANNUAL:
            salary["salary_period"] = "month"  # monthly figure filed as annual by the job board
    if salary["salary_min"] is None:
        salary["salary_min"] = salary["salary_max"]
    if salary["salary_max"] is None:
        salary["salary_max"] = salary["salary_min"]
    return salary, predicted


def enrich(job: Job) -> Job:
    """Return a copy of ``job`` with cleaned text and every derived field filled in."""
    description = strip_html(job.description)
    salary, predicted = _salary(job, description)
    exp_min, exp_max = extract_experience(description, job.experience_months)
    tags = [*job.tags, *([job.category] if job.category else [])]
    province, city, is_remote = resolve_location(job.location, job.location_area, job.title)
    low = to_annual_zar(salary["salary_min"], salary["salary_period"], salary["salary_currency"])
    high = to_annual_zar(salary["salary_max"], salary["salary_period"], salary["salary_currency"])
    if low is None or high is None:
        low = high = None
        predicted = False
    elif low > high:
        low, high = high, low
    return replace(
        job,
        company=(job.company or "").strip() or None,
        description=description,
        salary_min=salary["salary_min"],
        salary_max=salary["salary_max"],
        salary_currency=salary["salary_currency"],
        salary_period=salary["salary_period"],
        salary_is_predicted=predicted,
        salary_min_zar=low,
        salary_max_zar=high,
        employment_type=normalize_employment_type(job.employment_type_raw, job.title),
        seniority=infer_seniority(job.title, exp_min, job.employment_type_raw),
        experience_years_min=exp_min,
        experience_years_max=exp_max,
        skills=extract_skill_names(f"{job.title}\n{description}", tags),
        province=province,
        city=city,
        is_remote=is_remote,
        description_snippet=snippet(description),
    )
