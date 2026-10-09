from __future__ import annotations

import json
import os
from typing import Any

import boto3
import pytest
from moto import mock_aws

from sajobs import aws

REGION = "eu-west-1"
TABLE = "sa-jobmarket-test"
BUCKET = "sa-jobmarket-data-test"


@pytest.fixture(autouse=True)
def _env(monkeypatch):
    monkeypatch.setenv("AWS_DEFAULT_REGION", REGION)
    monkeypatch.setenv("AWS_REGION", REGION)
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "testing")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "testing")
    monkeypatch.setenv("AWS_SECURITY_TOKEN", "testing")
    monkeypatch.setenv("AWS_SESSION_TOKEN", "testing")
    monkeypatch.delenv("AWS_PROFILE", raising=False)
    monkeypatch.setenv("TABLE_NAME", TABLE)
    monkeypatch.setenv("DATA_BUCKET", BUCKET)
    aws.reset()
    yield


def create_table(dynamodb) -> Any:
    return dynamodb.create_table(
        TableName=TABLE,
        BillingMode="PROVISIONED",
        AttributeDefinitions=[
            {"AttributeName": n, "AttributeType": "S"}
            for n in ("PK", "SK", "GSI1PK", "GSI1SK", "GSI2PK", "GSI2SK")
        ],
        KeySchema=[{"AttributeName": "PK", "KeyType": "HASH"}, {"AttributeName": "SK", "KeyType": "RANGE"}],
        GlobalSecondaryIndexes=[
            {
                "IndexName": name,
                "KeySchema": [
                    {"AttributeName": f"{name}PK", "KeyType": "HASH"},
                    {"AttributeName": f"{name}SK", "KeyType": "RANGE"},
                ],
                "Projection": {"ProjectionType": "ALL"},
                "ProvisionedThroughput": {"ReadCapacityUnits": 5, "WriteCapacityUnits": 5},
            }
            for name in ("GSI1", "GSI2")
        ],
        ProvisionedThroughput={"ReadCapacityUnits": 10, "WriteCapacityUnits": 10},
        StreamSpecification={"StreamEnabled": True, "StreamViewType": "NEW_IMAGE"},
    )


class Cloud:
    """Handles to the mocked AWS resources a test needs."""

    def __init__(self):
        self.dynamodb = boto3.resource("dynamodb", region_name=REGION)
        self.table = create_table(self.dynamodb)
        self.s3 = boto3.client("s3", region_name=REGION)
        self.s3.create_bucket(Bucket=BUCKET, CreateBucketConfiguration={"LocationConstraint": REGION})
        self.sqs = boto3.client("sqs", region_name=REGION)
        self.dlq_url = self.sqs.create_queue(QueueName="jobs-dlq")["QueueUrl"]
        self.queue_url = self.sqs.create_queue(QueueName="jobs", Attributes={"VisibilityTimeout": "720"})["QueueUrl"]
        self.sns = boto3.client("sns", region_name=REGION)
        self.alerts_topic = self.sns.create_topic(Name="job-alerts")["TopicArn"]
        self.ssm = boto3.client("ssm", region_name=REGION)
        self.sfn = boto3.client("stepfunctions", region_name=REGION)
        self.state_machine = self.sfn.create_state_machine(
            name="pipeline",
            definition=json.dumps({"StartAt": "Done", "States": {"Done": {"Type": "Succeed"}}}),
            roleArn="arn:aws:iam::123456789012:role/test-role",
        )["stateMachineArn"]
        os.environ.update(
            {
                "QUEUE_URL": self.queue_url,
                "DLQ_URL": self.dlq_url,
                "ALERTS_TOPIC_ARN": self.alerts_topic,
                "STATE_MACHINE_ARN": self.state_machine,
            }
        )

    def queue_messages(self, url: str | None = None) -> list[dict[str, Any]]:
        messages = []
        while True:
            batch = self.sqs.receive_message(
                QueueUrl=url or self.queue_url, MaxNumberOfMessages=10, AttributeNames=["All"]
            ).get("Messages", [])
            if not batch:
                return messages
            messages.extend(batch)

    def keys(self, prefix: str = "") -> list[str]:
        return [o["Key"] for o in self.s3.list_objects_v2(Bucket=BUCKET, Prefix=prefix).get("Contents", [])]


@pytest.fixture
def cloud(monkeypatch):
    with mock_aws():
        c = Cloud()
        for name in ("QUEUE_URL", "DLQ_URL", "ALERTS_TOPIC_ARN", "STATE_MACHINE_ARN"):
            monkeypatch.setenv(name, os.environ[name])
        yield c


def api_event(
    route_key: str,
    *,
    path: dict[str, str] | None = None,
    query: dict[str, str] | None = None,
    body: Any = None,
    claims: dict[str, Any] | None = None,
) -> dict[str, Any]:
    event: dict[str, Any] = {
        "version": "2.0",
        "routeKey": route_key,
        "rawPath": route_key.split(" ", 1)[1],
        "pathParameters": path,
        "queryStringParameters": query,
        "requestContext": {"http": {"method": route_key.split(" ", 1)[0]}},
        "isBase64Encoded": False,
    }
    if body is not None:
        event["body"] = body if isinstance(body, str) else json.dumps(body)
    if claims is not None:
        event["requestContext"]["authorizer"] = {"jwt": {"claims": claims, "scopes": None}}
    return event


def body_of(response: dict[str, Any]) -> Any:
    return json.loads(response["body"]) if response.get("body") else None


USER_A = {"sub": "11111111-aaaa-4aaa-8aaa-111111111111", "email": "a@example.com"}
USER_B = {"sub": "22222222-bbbb-4bbb-8bbb-222222222222", "email": "b@example.com"}
ADMIN = {"sub": "33333333-cccc-4ccc-8ccc-333333333333", "email": "admin@example.com", "cognito:groups": "[admins]"}
