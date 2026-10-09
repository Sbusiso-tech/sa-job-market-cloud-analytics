"""Lazily created, cached boto3 clients (cached per Lambda container; tests call ``reset()``)."""
from __future__ import annotations

import os
from functools import cache

import boto3
from botocore.config import Config

_CONFIG = Config(retries={"mode": "adaptive", "max_attempts": 10}, connect_timeout=5, read_timeout=30)


@cache
def client(name: str):
    return boto3.client(name, config=_CONFIG)


@cache
def table(name: str | None = None):
    return boto3.resource("dynamodb", config=_CONFIG).Table(name or os.environ["TABLE_NAME"])


def reset() -> None:
    client.cache_clear()
    table.cache_clear()
