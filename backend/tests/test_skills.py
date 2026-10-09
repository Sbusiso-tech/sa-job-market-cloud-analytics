import pytest

from sajobs.skills import canonical_skill, extract_skill_names, extract_skills, load_taxonomy, skill_list


def names(text, tags=None):
    return {s["skill"] for s in extract_skills(text, tags)}


def test_taxonomy_loads_and_names_are_unique():
    skills = load_taxonomy()
    assert len(skills) > 100
    assert len({s.name.lower() for s in skills}) == len(skills)


@pytest.mark.parametrize(
    "text, expected",
    [
        ("Strong Python and SQL skills", {"Python", "SQL"}),
        ("Experience with C++ and C#", {"C++", "C#"}),
        ("Proficient in C/C++", {"C", "C++"}),
        ("Node.js, React.js and TypeScript", {"Node.js", "React", "TypeScript"}),
        ("PostgreSQL and NoSQL stores", {"PostgreSQL", "NoSQL"}),
        ("Build ETL pipelines with PySpark on Databricks", {"ETL", "Apache Spark", "Databricks"}),
        ("CI/CD with GitHub Actions, Docker and k8s", {"CI/CD", "GitHub", "GitHub Actions", "Docker", "Kubernetes"}),
        ("Python, R or SAS for statistics", {"Python", "R", "SAS", "Statistics"}),
        ("Golang microservices", {"Go", "Microservices"}),
        ("Power BI dashboards and Excel", {"Power BI", "Excel"}),
    ],
)
def test_extract_from_text(text, expected):
    assert names(text) == expected


@pytest.mark.parametrize(
    "text, expected",
    [
        ("SAP ABAP developer for the S/4HANA migration", {"SAP", "SAP ABAP", "SAP S/4HANA"}),
        ("Payroll on Sage Pastel and Syspro ERP", {"Sage Pastel", "Syspro"}),
        ("Salesforce and Microsoft Dynamics 365 consultant", {"Salesforce", "Dynamics 365"}),
        ("ServiceNow admin, ITIL v4 certified", {"ServiceNow", "ITIL"}),
        ("CompTIA A+ and CCNA required", {"CompTIA", "CCNA"}),
        ("Pega PRPC case management", {"Pega"}),
    ],
)
def test_south_african_skills(text, expected):
    assert names(text) == expected


@pytest.mark.parametrize(
    "text",
    [
        "Java",  # must not also match JavaScript
        "We go above and beyond for our customers",
        "Our postgresql cluster",  # must not also match SQL
        "You excel at communication and ensure the rest of the team succeeds",
        "Take a sap break and rest",  # lower-case "sap", "rest" are not skills
        "A sage piece of advice",
    ],
)
def test_avoids_false_positives(text):
    found = names(text)
    assert not found & {"JavaScript", "Go", "SQL", "Excel", "REST APIs", "SAP", "Sage Pastel"}


def test_tags_are_matched_including_tag_only_aliases():
    assert names("", ["python", "go", "c", "Typescript ", "ruby/rails"]) == {"Python", "Go", "C", "TypeScript"}


def test_canonical_skill_and_list():
    assert canonical_skill("  power bi ") == "Power BI"
    assert canonical_skill("sap s/4hana") == "SAP S/4HANA"
    assert canonical_skill("cobol-ish") is None
    assert canonical_skill(42) is None
    listing = skill_list()
    assert {"name": "Python", "category": "Programming Language"} in listing
    assert [s["name"].lower() for s in listing] == sorted(s["name"].lower() for s in listing)
    assert extract_skill_names("Python and SQL") == ["Python", "SQL"]
