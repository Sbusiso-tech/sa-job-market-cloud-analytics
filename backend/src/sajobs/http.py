"""Helpers for API Gateway HTTP API (payload format 2.0) Lambda handlers."""
from __future__ import annotations

import base64
import json
import logging
from collections.abc import Callable
from typing import Any

log = logging.getLogger(__name__)

PUBLIC_CACHE = "public, max-age=900"
PRIVATE_CACHE = "no-store"
MAX_BODY_BYTES = 10 * 1024

ERROR_CODES = {400: "bad_request", 401: "unauthorized", 403: "forbidden", 404: "not_found", 409: "limit_reached",
               500: "internal"}


class ApiError(Exception):
    def __init__(self, status: int, message: str, code: str | None = None):
        super().__init__(message)
        self.status = status
        self.code = code or ERROR_CODES.get(status, "bad_request")
        self.message = message


def json_response(status: int, body: Any, cache: str = PRIVATE_CACHE) -> dict[str, Any]:
    return {
        "statusCode": status,
        "headers": {
            "Content-Type": "application/json",
            "Cache-Control": cache,
            "X-Content-Type-Options": "nosniff",
        },
        "body": json.dumps(body, separators=(",", ":"), ensure_ascii=False),
    }


def no_content() -> dict[str, Any]:
    return {"statusCode": 204, "headers": {"Cache-Control": PRIVATE_CACHE}, "body": ""}


def error_response(status: int, code: str, message: str) -> dict[str, Any]:
    return json_response(status, {"error": {"code": code, "message": message}}, PRIVATE_CACHE)


def route_key(event: dict[str, Any]) -> str:
    return event.get("routeKey") or ""


def path_param(event: dict[str, Any], name: str) -> str:
    value = (event.get("pathParameters") or {}).get(name)
    if not value:
        raise ApiError(400, f"Missing path parameter {name}")
    return value


def query_params(event: dict[str, Any]) -> dict[str, str]:
    return dict(event.get("queryStringParameters") or {})


def parse_json_body(event: dict[str, Any]) -> dict[str, Any]:
    raw = event.get("body") or ""
    if event.get("isBase64Encoded") and raw:
        try:
            raw = base64.b64decode(raw).decode("utf-8")
        except (ValueError, UnicodeDecodeError) as exc:
            raise ApiError(400, "Body must be UTF-8 JSON") from exc
    if len(raw.encode("utf-8")) > MAX_BODY_BYTES:
        raise ApiError(400, "Request body too large")
    if not raw.strip():
        raise ApiError(400, "Request body is required")
    try:
        body = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ApiError(400, "Body must be valid JSON") from exc
    if not isinstance(body, dict):
        raise ApiError(400, "Body must be a JSON object")
    return body


def get_claims(event: dict[str, Any]) -> dict[str, Any]:
    authorizer = (event.get("requestContext") or {}).get("authorizer") or {}
    return dict((authorizer.get("jwt") or {}).get("claims") or {})


def get_groups(claims: dict[str, Any]) -> list[str]:
    """``cognito:groups`` arrives as a list or as a string such as ``"[admins]"`` / ``"[admins users]"``."""
    raw = claims.get("cognito:groups")
    if raw is None:
        return []
    if isinstance(raw, (list, tuple)):
        return [str(g).strip() for g in raw if str(g).strip()]
    text = str(raw).strip()
    if text.startswith("["):
        try:
            parsed = json.loads(text)
            if isinstance(parsed, list):
                return [str(g).strip() for g in parsed if str(g).strip()]
        except json.JSONDecodeError:
            pass
        text = text.strip("[]")
    return [g.strip().strip('"') for g in text.replace(",", " ").split() if g.strip().strip('"')]


def require_sub(claims: dict[str, Any]) -> str:
    sub = claims.get("sub")
    if not sub or not isinstance(sub, str):
        raise ApiError(401, "Missing or invalid token", "unauthorized")
    return sub


Handler = Callable[[dict[str, Any]], dict[str, Any]]


def dispatch(event: dict[str, Any], routes: dict[str, Handler]) -> dict[str, Any]:
    """Call the handler for the event's route key and turn errors into the contract's JSON error shape."""
    key = route_key(event)
    handler = routes.get(key)
    try:
        if handler is None:
            raise ApiError(404, "Route not found")
        return handler(event)
    except ApiError as exc:
        return error_response(exc.status, exc.code, exc.message)
    except Exception:
        log.exception("unhandled error on route %s", key)
        return error_response(500, "internal", "Internal server error")
