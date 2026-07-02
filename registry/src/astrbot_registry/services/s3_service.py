"""SeaweedFS S3 operations."""

import boto3
from botocore.client import Config
from botocore.exceptions import ClientError

from ..config import settings


def get_s3_client() -> boto3.client:
    return boto3.client(
        "s3",
        endpoint_url=settings.s3_endpoint,
        aws_access_key_id=settings.s3_access_key,
        aws_secret_access_key=settings.s3_secret_key,
        region_name=settings.s3_region,
        config=Config(signature_version="s3v4"),
    )


def ensure_bucket_exists() -> None:
    """Create the configured S3 bucket if it does not exist yet."""
    client = get_s3_client()
    try:
        client.head_bucket(Bucket=settings.s3_bucket)
    except ClientError as exc:
        error_code = exc.response["Error"]["Code"]
        if error_code == "404":
            client.create_bucket(Bucket=settings.s3_bucket)
        else:
            raise
