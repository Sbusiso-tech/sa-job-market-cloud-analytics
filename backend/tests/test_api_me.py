from datetime import UTC, datetime

import pytest

from conftest import USER_A, USER_B, api_event, body_of
from handlers import api_me
from helpers import seed_jobs
from sajobs.repository import Repository

NOW = datetime.now(UTC)


def call(route, claims=USER_A, **kwargs):
    return api_me.handler(api_event(route, claims=claims, **kwargs))


def create_alert(body, claims=USER_A):
    return call("POST /api/me/alerts", claims=claims, body=body)


def subscriptions(cloud):
    return cloud.sns.list_subscriptions_by_topic(TopicArn=cloud.alerts_topic)["Subscriptions"]


# ------------------------------------------------------------------ auth


@pytest.mark.parametrize(
    "route, path",
    [
        ("GET /api/me/saved-jobs", None),
        ("PUT /api/me/saved-jobs/{job_id}", {"job_id": "abc"}),
        ("DELETE /api/me/saved-jobs/{job_id}", {"job_id": "abc"}),
        ("GET /api/me/alerts", None),
        ("POST /api/me/alerts", None),
        ("DELETE /api/me/alerts/{alert_id}", {"alert_id": "abc"}),
        ("DELETE /api/me", None),
    ],
)
def test_every_route_requires_verified_sub(cloud, route, path):
    response = api_me.handler(api_event(route, path=path, body={"skills": ["Python"]}))
    assert response["statusCode"] == 401
    assert body_of(response)["error"]["code"] == "unauthorized"


# ------------------------------------------------------------ saved jobs


def test_save_list_unsave(cloud):
    job_id = seed_jobs(cloud.table, NOW)[0]["job_id"]
    response = call("PUT /api/me/saved-jobs/{job_id}", path={"job_id": job_id})
    assert response["statusCode"] == 200
    assert response["headers"]["Cache-Control"] == "no-store"
    saved = body_of(response)
    assert set(saved) == {"job_id", "title", "company", "province", "saved_at"}
    again = body_of(call("PUT /api/me/saved-jobs/{job_id}", path={"job_id": job_id}))
    assert again == saved  # idempotent

    assert body_of(call("GET /api/me/saved-jobs")) == {"items": [saved]}
    assert body_of(call("GET /api/me/saved-jobs", claims=USER_B)) == {"items": []}

    assert call("DELETE /api/me/saved-jobs/{job_id}", path={"job_id": job_id})["statusCode"] == 204
    assert call("DELETE /api/me/saved-jobs/{job_id}", path={"job_id": job_id})["statusCode"] == 204
    assert body_of(call("GET /api/me/saved-jobs")) == {"items": []}


def test_save_unknown_job_is_404(cloud):
    response = call("PUT /api/me/saved-jobs/{job_id}", path={"job_id": "f" * 40})
    assert response["statusCode"] == 404 and body_of(response)["error"]["code"] == "not_found"
    assert call("PUT /api/me/saved-jobs/{job_id}", path={"job_id": "a/b"})["statusCode"] == 404


def test_user_cannot_touch_other_users_items(cloud):
    job_id = seed_jobs(cloud.table, NOW)[0]["job_id"]
    call("PUT /api/me/saved-jobs/{job_id}", path={"job_id": job_id})
    alert = body_of(create_alert({"skills": ["Python"]}))["alert"]

    # B deleting A's saved job / alert id only touches B's own partition
    call("DELETE /api/me/saved-jobs/{job_id}", claims=USER_B, path={"job_id": job_id})
    call("DELETE /api/me/alerts/{alert_id}", claims=USER_B, path={"alert_id": alert["alert_id"]})
    call("DELETE /api/me", claims=USER_B)
    assert len(body_of(call("GET /api/me/saved-jobs"))["items"]) == 1
    assert len(body_of(call("GET /api/me/alerts"))["alerts"]) == 1
    assert body_of(call("GET /api/me/alerts", claims=USER_B))["alerts"] == []

    # a sub smuggled in the body or query is ignored
    body_of(create_alert({"skills": ["SQL"], "sub": USER_B["sub"]}))
    assert body_of(call("GET /api/me/alerts", claims=USER_B))["alerts"] == []

    items = cloud.table.scan()["Items"]
    user_pks = {i["PK"] for i in items if i["PK"].startswith("USER#")}
    assert user_pks == {f"USER#{USER_A['sub']}"}


# ---------------------------------------------------------------- alerts


def test_first_alert_subscribes_email_with_filter_policy(cloud):
    response = create_alert({"skills": ["python", "AWS", "python"], "province": "gauteng"})
    assert response["statusCode"] == 201
    body = body_of(response)
    assert body["alert"]["skills"] == ["Python", "AWS"] and body["alert"]["province"] == "Gauteng"
    assert set(body["alert"]) == {"alert_id", "skills", "province", "created_at"}
    assert body["subscription_status"] in {"pending_confirmation", "confirmed"}

    subs = subscriptions(cloud)
    assert len(subs) == 1 and subs[0]["Endpoint"] == USER_A["email"] and subs[0]["Protocol"] == "email"
    attributes = cloud.sns.get_subscription_attributes(SubscriptionArn=subs[0]["SubscriptionArn"])["Attributes"]
    assert attributes["FilterPolicy"] == '{"user_sub": ["' + USER_A["sub"] + '"]}'
    assert attributes["FilterPolicyScope"] == "MessageAttributes"

    create_alert({"skills": ["SQL"]})
    assert len(subscriptions(cloud)) == 1  # second alert re-uses the subscription
    profile = Repository(cloud.table).get_profile(USER_A["sub"])
    assert profile["subscription_arn"] == subs[0]["SubscriptionArn"] and profile["email"] == USER_A["email"]

    listing = body_of(call("GET /api/me/alerts"))
    assert listing["email"] == USER_A["email"]
    assert listing["subscription_status"] in {"pending_confirmation", "confirmed"}
    assert [a["skills"] for a in listing["alerts"]] == [["Python", "AWS"], ["SQL"]]
    assert listing["alerts"][1]["province"] is None


def test_alert_list_without_alerts(cloud):
    assert body_of(call("GET /api/me/alerts")) == {"email": USER_A["email"], "subscription_status": "none",
                                                   "alerts": []}


def test_pending_status_reported(cloud, monkeypatch):
    create_alert({"skills": ["Python"]})
    real = api_me.aws.client("sns")

    class PendingSns:
        def get_subscription_attributes(self, **kwargs):
            return {"Attributes": {"PendingConfirmation": "true"}}

        def __getattr__(self, name):
            return getattr(real, name)

    monkeypatch.setattr(api_me.aws, "client", lambda name: PendingSns())
    assert body_of(call("GET /api/me/alerts"))["subscription_status"] == "pending_confirmation"


@pytest.mark.parametrize(
    "body",
    [
        {},
        {"skills": []},
        {"skills": "Python"},
        {"skills": ["Python"] * 6},
        {"skills": ["Klingon"]},
        {"skills": [42]},
        {"skills": ["Python"], "province": "Atlantis"},
        "not json",
        [1, 2],
    ],
)
def test_alert_validation(cloud, body):
    response = create_alert(body)
    assert response["statusCode"] == 400
    assert body_of(response)["error"]["code"] == "bad_request"


def test_alert_requires_email_claim(cloud):
    response = create_alert({"skills": ["Python"]}, claims={"sub": USER_A["sub"]})
    assert response["statusCode"] == 400


def test_max_five_alerts(cloud):
    for _ in range(5):
        assert create_alert({"skills": ["Python"]})["statusCode"] == 201
    response = create_alert({"skills": ["SQL"]})
    assert response["statusCode"] == 409
    assert body_of(response)["error"]["code"] == "limit_reached"


def test_deleting_last_alert_unsubscribes(cloud):
    first = body_of(create_alert({"skills": ["Python"]}))["alert"]["alert_id"]
    second = body_of(create_alert({"skills": ["SQL"]}))["alert"]["alert_id"]
    assert call("DELETE /api/me/alerts/{alert_id}", path={"alert_id": first})["statusCode"] == 204
    assert len(subscriptions(cloud)) == 1
    assert Repository(cloud.table).alerts_for_skill("Python") == []
    assert call("DELETE /api/me/alerts/{alert_id}", path={"alert_id": second})["statusCode"] == 204
    assert subscriptions(cloud) == []
    assert Repository(cloud.table).get_profile(USER_A["sub"])["subscription_arn"] is None
    assert call("DELETE /api/me/alerts/{alert_id}", path={"alert_id": "missing"})["statusCode"] == 204
    assert call("DELETE /api/me/alerts/{alert_id}", path={"alert_id": "../x"})["statusCode"] == 404

    # a new alert subscribes again
    create_alert({"skills": ["Excel"]})
    assert len(subscriptions(cloud)) == 1


def test_delete_me_removes_everything(cloud):
    job_id = seed_jobs(cloud.table, NOW)[0]["job_id"]
    call("PUT /api/me/saved-jobs/{job_id}", path={"job_id": job_id})
    create_alert({"skills": ["Python", "SQL"]})
    assert call("DELETE /api/me")["statusCode"] == 204
    items = cloud.table.scan()["Items"]
    assert not [i for i in items if i["PK"].startswith(("USER#", "ALERTIDX#"))]
    assert subscriptions(cloud) == []
    assert call("DELETE /api/me")["statusCode"] == 204  # idempotent


def test_sns_errors_are_tolerated(cloud, monkeypatch):
    from botocore.exceptions import ClientError

    create_alert({"skills": ["Python"]})
    real = api_me.aws.client("sns")

    class FlakySns:
        def unsubscribe(self, **kwargs):
            raise ClientError({"Error": {"Code": "InvalidParameter", "Message": "pending"}}, "Unsubscribe")

        def get_subscription_attributes(self, **kwargs):
            raise ClientError({"Error": {"Code": "NotFound", "Message": "gone"}}, "GetSubscriptionAttributes")

        def __getattr__(self, name):
            return getattr(real, name)

    monkeypatch.setattr(api_me.aws, "client", lambda name: FlakySns())
    assert body_of(call("GET /api/me/alerts"))["subscription_status"] == "none"
    assert call("DELETE /api/me")["statusCode"] == 204
