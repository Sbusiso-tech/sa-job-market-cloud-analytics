from datetime import UTC, datetime

from boto3.dynamodb.types import TypeSerializer

from handlers import alert_matcher
from helpers import curated, make_job
from sajobs.repository import Repository

NOW = datetime(2026, 10, 9, 5, 0, tzinfo=UTC)
_ser = TypeSerializer()


def stream_event(items, event_name="INSERT"):
    return {
        "Records": [
            {"eventName": event_name, "dynamodb": {"NewImage": {k: _ser.serialize(v) for k, v in item.items()}}}
            for item in items
        ]
    }


def job_item(**overrides):
    return Repository.job_item(curated(make_job(**overrides), NOW), NOW)


class FakeSns:
    def __init__(self):
        self.published = []

    def publish(self, **kwargs):
        self.published.append(kwargs)
        return {"MessageId": "1"}


def test_digest_per_user_with_skill_and_province_rules(cloud, monkeypatch):
    repo = Repository(cloud.table)
    repo.create_alert("user-a", "a1", ["Python"], None, NOW)  # any province
    repo.create_alert("user-a", "a2", ["SQL"], "Gauteng", NOW)  # same jobs again -> listed once
    repo.create_alert("user-b", "b1", ["Python"], "Western Cape", NOW)  # wrong province
    repo.create_alert("user-c", "c1", ["Java"], None, NOW)  # no matching skill
    sns = FakeSns()
    monkeypatch.setattr(alert_matcher.aws, "client", lambda name: sns)

    jobs = [job_item(source_id=str(i), title=f"Python Developer {i}") for i in range(12)]
    result = alert_matcher.handler(stream_event(jobs))
    assert result == {"jobs": 12, "digests": 1}
    message = sns.published[0]
    assert message["MessageAttributes"] == {"user_sub": {"DataType": "String", "StringValue": "user-a"}}
    assert message["Subject"] == "12 new jobs match your SA job alerts"
    assert message["Message"].count("* Python Developer") == 10
    assert "...and 2 more" in message["Message"]
    assert "R600 000 - R780 000 per year" in message["Message"]
    assert "Gauteng" in message["Message"] and "https://www.adzuna.co.za/details/1" in message["Message"]


def test_ignores_non_inserts_and_non_jobs(cloud):
    assert alert_matcher.handler(stream_event([job_item()], "MODIFY")) == {"jobs": 0, "digests": 0}
    assert alert_matcher.handler(stream_event([{"PK": "STATS#LATEST", "SK": "X"}])) == {"jobs": 0, "digests": 0}
    assert alert_matcher.handler({"Records": [{"eventName": "INSERT", "dynamodb": {}}]})["jobs"] == 0


def test_publishes_to_real_topic(cloud):
    Repository(cloud.table).create_alert("user-a", "a1", ["AWS"], "Gauteng", NOW)
    assert alert_matcher.handler(stream_event([job_item()]))["digests"] == 1


def test_salary_text_and_single_job_subject():
    assert alert_matcher.salary_text({}) == "Salary not stated"
    assert alert_matcher.salary_text({"salary_min_zar": 500000, "salary_max_zar": 500000}) == "R500 000 per year"
    estimated = alert_matcher.salary_text({"salary_min_zar": None, "salary_max_zar": 1, "salary_is_predicted": True})
    assert estimated == "R1 per year (estimated)"
    subject, body = alert_matcher.build_digest([{"title": "X", "company": None}])
    assert subject == "1 new job match your SA job alerts"
    assert "Company not stated" in body
