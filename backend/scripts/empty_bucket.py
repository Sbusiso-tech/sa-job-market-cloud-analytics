"""Delete every object (and every version / delete marker, if versioning was ever enabled) from S3 buckets.

Used by ``make destroy`` before ``sam delete``: CloudFormation cannot delete non-empty buckets.
Usage: python empty_bucket.py <bucket> [<bucket> ...]
"""
from __future__ import annotations

import sys

import boto3
from botocore.exceptions import ClientError


def empty(name: str) -> None:
    bucket = boto3.resource("s3").Bucket(name)
    try:
        bucket.object_versions.delete()
        bucket.objects.all().delete()
    except ClientError as exc:
        if exc.response["Error"]["Code"] == "NoSuchBucket":
            print(f"{name}: already gone")
            return
        raise
    print(f"{name}: emptied")


if __name__ == "__main__":
    for arg in sys.argv[1:]:
        if arg and arg != "None":
            empty(arg)
