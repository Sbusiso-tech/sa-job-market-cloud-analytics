import pytest

from helpers import make_job
from sajobs.transform import (
    annualize,
    enrich,
    extract_experience,
    find_rand_salary,
    guess_period,
    infer_seniority,
    normalize_employment_type,
    normalize_period,
    parse_salary_text,
    snippet,
    strip_html,
    to_annual_zar,
)


@pytest.mark.parametrize(
    "text, expected",
    [
        ("$90k - $105k", (90_000, 105_000, "USD", "year")),
        ("$45-$120/Hour", (45, 120, "USD", "hour")),
        ("$35,3k- $52k", (35_300, 52_000, "USD", "year")),
        ("€60.000 - €75.000 per year", (60_000, 75_000, "EUR", "year")),
        ("£50,000", (50_000, 50_000, "GBP", "year")),
        ("R45 000 - R55 000 per month", (45_000, 55_000, "ZAR", "month")),
        ("R35 000 per month", (35_000, 35_000, "ZAR", "month")),
        ("R450k p.a.", (450_000, 450_000, "ZAR", "year")),
        ("R 25,000 - R 30,000 pm", (25_000, 30_000, "ZAR", "month")),
        ("R600 000 CTC", (600_000, 600_000, "ZAR", "year")),
        ("R40 000 CTC", (40_000, 40_000, "ZAR", "month")),
        ("R1.2m p.a.", (1_200_000, 1_200_000, "ZAR", "year")),
        ("R250 per hour", (250, 250, "ZAR", "hour")),
        ("R 25 000,00 pm", (25_000, 25_000, "ZAR", "month")),
        ("ZAR 1500 per day", (1_500, 1_500, "ZAR", "day")),
        ("R8 000 per week", (8_000, 8_000, "ZAR", "week")),
        ("R30 000 per month for 12 months", (30_000, 30_000, "ZAR", "month")),
    ],
)
def test_parse_salary_text(text, expected):
    result = parse_salary_text(text)
    assert (result["salary_min"], result["salary_max"], result["salary_currency"], result["salary_period"]) == expected


@pytest.mark.parametrize("text", [None, "", "Competitive", "Market related"])
def test_parse_salary_text_without_numbers(text):
    assert parse_salary_text(text)["salary_min"] is None


def test_parse_salary_text_default_currency_and_garbage_numbers():
    assert parse_salary_text("35000 monthly", default_currency="ZAR")["salary_currency"] == "ZAR"
    assert parse_salary_text("abc 0")["salary_min"] is None


@pytest.mark.parametrize(
    "text, expected",
    [
        ("Great role. Salary: R35 000 - R40 000 per month CTC. Apply now", "R35 000 - R40 000 per month CTC"),
        ("Pays R450k p.a. plus bonus", "R450k p.a."),
        ("Remuneration R 25,000 - R 30,000 pm", "R 25,000 - R 30,000 pm"),
        ("No salary here, see our R&D team", None),
        (None, None),
    ],
)
def test_find_rand_salary(text, expected):
    assert find_rand_salary(text) == expected


def test_guess_period():
    assert guess_period(300, "ZAR") == "hour"
    assert guess_period(45_000, "ZAR") == "month"
    assert guess_period(450_000, "ZAR") == "year"
    assert guess_period(100, "USD") == "hour"
    assert guess_period(5_000, None) == "month"
    assert guess_period(90_000, "USD") == "year"


def test_annualize_and_zar():
    assert annualize(50, "hour") == 104_000
    assert annualize(40_000, "month") == 480_000
    assert annualize(1_000, "day") == 260_000
    assert annualize(5_000, "week") == 260_000
    assert annualize(None, "hour") is None
    assert to_annual_zar(35_000, "month", "ZAR") == 420_000
    assert to_annual_zar(35_000, "month", "USD") is None
    assert to_annual_zar(500, "year", "ZAR") is None
    assert to_annual_zar(None, "year", "ZAR") is None


def test_normalize_period():
    assert normalize_period("Annual") == "year"
    assert normalize_period("monthly") == "month"
    assert normalize_period(None) is None
    assert normalize_period("fortnight") is None


@pytest.mark.parametrize(
    "raw, title, expected",
    [
        ("full_time", None, "full_time"),
        ("FULLTIME", None, "full_time"),
        ("freelance", None, "contract"),
        ("permanent, full_time", None, "full_time"),
        ("part_time", None, "part_time"),
        ("Fixed term", None, "contract"),
        ("temp", None, "temporary"),
        (None, "Data Engineering Intern", "internship"),
        (None, "IT Learnership 2027", "internship"),
        (None, "Data Engineer", "unspecified"),
    ],
)
def test_normalize_employment_type(raw, title, expected):
    assert normalize_employment_type(raw, title) == expected


@pytest.mark.parametrize(
    "text, expected",
    [
        ("You have 3-5 years of experience with Python.", (3, 5)),
        ("Minimum of 4 years experience in data engineering", (4, 4)),
        ("5+ years building pipelines", (5, 5)),
        ("2 years of professional experience", (2, 2)),
        ("We have been around for 150 years", (None, None)),
        ("No experience required", (None, None)),
        ("", (None, None)),
    ],
)
def test_extract_experience(text, expected):
    assert extract_experience(text) == expected


def test_extract_experience_prefers_structured_months():
    assert extract_experience("10+ years", months=36) == (3, 3)


@pytest.mark.parametrize(
    "title, years, expected",
    [
        ("Senior Data Engineer", None, "senior"),
        ("Lead Analytics Engineer", None, "lead"),
        ("Junior Python Developer", None, "junior"),
        ("Intermediate Developer", None, "mid"),
        ("IT Support Intern", None, "intern"),
        ("Data Engineer", 1, "junior"),
        ("Data Engineer", 3, "mid"),
        ("Data Engineer", 7, "senior"),
        ("Data Engineer", None, "unspecified"),
    ],
)
def test_infer_seniority(title, years, expected):
    assert infer_seniority(title, years) == expected


def test_strip_html_and_snippet():
    assert strip_html("<p>Hello&nbsp;<b>world</b></p><ul><li>SQL</li></ul>") == "Hello world\nSQL"
    assert strip_html(None) == ""
    assert snippet(None) is None
    assert snippet("short text") == "short text"
    long = snippet("word " * 200)
    assert len(long) <= 300 and long.endswith("…")


def test_enrich_end_to_end():
    job = enrich(make_job())
    assert job.company == "Acme Bank"
    assert (job.province, job.city, job.is_remote) == ("Gauteng", "Sandton", False)
    assert job.seniority == "senior"
    assert job.employment_type == "full_time"
    assert job.experience_years_min == 5
    assert (job.salary_min_zar, job.salary_max_zar) == (600_000, 780_000)
    assert job.skills == ["AWS", "Python", "SQL"]
    assert job.description_snippet.startswith("5+ years")


def test_enrich_parses_rand_salary_from_description_when_structured_missing():
    job = enrich(
        make_job(
            salary_min=None,
            salary_max=None,
            salary_currency=None,
            salary_period=None,
            salary_is_predicted=True,
            description="Python developer. Salary: R35 000 - R40 000 per month CTC.",
        )
    )
    assert (job.salary_min_zar, job.salary_max_zar, job.salary_is_predicted) == (420_000, 480_000, False)


def test_enrich_treats_monthly_figure_filed_as_annual():
    job = enrich(make_job(salary_min=30_000.0, salary_max=35_000.0))
    assert (job.salary_min_zar, job.salary_max_zar) == (360_000, 420_000)


def test_enrich_drops_implausible_or_foreign_salary():
    assert enrich(make_job(salary_min=1.0, salary_max=2.0, salary_period="year")).salary_min_zar is None
    usd = enrich(make_job(salary_currency="USD"))
    assert (usd.salary_min_zar, usd.salary_is_predicted) == (None, False)


def test_enrich_single_sided_salary_and_swapped_range():
    one = enrich(make_job(salary_min=None, salary_max=500_000.0))
    assert (one.salary_min_zar, one.salary_max_zar) == (500_000, 500_000)
    swapped = enrich(make_job(salary_min=800_000.0, salary_max=600_000.0))
    assert (swapped.salary_min_zar, swapped.salary_max_zar) == (600_000, 800_000)


def test_enrich_remote_and_category_tags():
    job = enrich(make_job(location="Remote", location_area=[], category="IT Jobs", title="Remote Python Developer"))
    assert (job.province, job.is_remote, job.city) == ("Remote", True, None)
