import base64
import json

import pytest

from conftest import api_event, body_of
from sajobs.http import (
    ApiError,
    dispatch,
    error_response,
    get_claims,
    get_groups,
    json_response,
    no_content,
    parse_json_body,
    path_param,
    require_sub,
)


@pytest.mark.parametrize(
    "raw, expected",
    [
        ("[admins]", ["admins"]),
        ("[admins users]", ["admins", "users"]),
        ('["admins","users"]', ["admins", "users"]),
        ("admins", ["admins"]),
        (["admins"], ["admins"]),
        ("[]", []),
        (None, []),
        ("[admins, users]", ["admins", "users"]),
    ],
)
def test_get_groups(raw, expected):
    claims = {} if raw is None else {"cognito:groups": raw}
    assert get_groups(claims) == expected


def test_responses():
    response = json_response(200, {"a": 1}, "public, max-age=900")
    assert response["headers"]["Cache-Control"] == "public, max-age=900"
    assert body_of(response) == {"a": 1}
    assert no_content()["statusCode"] == 204
    error = error_response(404, "not_found", "Nope")
    assert body_of(error) == {"error": {"code": "not_found", "message": "Nope"}}
    assert error["headers"]["Cache-Control"] == "no-store"


def test_parse_json_body():
    assert parse_json_body({"body": '{"a": 1}'}) == {"a": 1}
    encoded = base64.b64encode(b'{"b": 2}').decode()
    assert parse_json_body({"body": encoded, "isBase64Encoded": True}) == {"b": 2}
    for event in ({"body": ""}, {"body": "[1]"}, {"body": "{bad"}, {"body": "x" * 20_000},
                  {"body": "%%%", "isBase64Encoded": True}):
        with pytest.raises(ApiError) as err:
            parse_json_body(event)
        assert err.value.status == 400


def test_claims_and_path_params():
    event = api_event("GET /x", claims={"sub": "abc"}, path={"id": "1"})
    assert get_claims(event) == {"sub": "abc"}
    assert get_claims({}) == {}
    assert path_param(event, "id") == "1"
    with pytest.raises(ApiError):
        path_param(event, "missing")
    assert require_sub({"sub": "abc"}) == "abc"
    with pytest.raises(ApiError) as err:
        require_sub({})
    assert err.value.code == "unauthorized"


def test_dispatch_handles_unknown_routes_and_crashes():
    def boom(event):
        raise RuntimeError("secret detail")

    assert dispatch(api_event("GET /nope"), {})["statusCode"] == 404
    response = dispatch(api_event("GET /boom"), {"GET /boom": boom})
    assert response["statusCode"] == 500
    assert "secret" not in response["body"]
    assert json.loads(response["body"])["error"]["code"] == "internal"
