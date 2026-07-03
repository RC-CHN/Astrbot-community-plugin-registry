"""SeaweedFS S3 operations."""

import asyncio
from pathlib import Path
from typing import Any

import boto3
from botocore.client import Config
from botocore.exceptions import ClientError

from ..config import settings


def get_s3_client() -> Any:
    return boto3.client(
        "s3",
        endpoint_url=settings.s3_endpoint,
        aws_access_key_id=settings.s3_access_key,
        aws_secret_access_key=settings.s3_secret_key,
        region_name=settings.s3_region,
        config=Config(
            signature_version="s3v4",
            connect_timeout=settings.s3_connect_timeout,
            read_timeout=settings.s3_read_timeout,
            retries={"max_attempts": settings.s3_max_attempts},
        ),
    )


def ensure_bucket_exists() -> None:
    """Create the configured S3 bucket if it does not exist yet."""
    from botocore.exceptions import BotoCoreError

    try:
        client = get_s3_client()
        client.head_bucket(Bucket=settings.s3_bucket)
    except ClientError as exc:
        error_code = exc.response["Error"]["Code"]
        if error_code in ("404", "NoSuchBucket"):
            client.create_bucket(Bucket=settings.s3_bucket)
        else:
            raise
    except BotoCoreError:
        import logging

        logger = logging.getLogger(__name__)
        logger.warning("Could not connect to S3 endpoint; skipping bucket creation")


async def upload_file(local_path: Path, s3_key: str) -> None:
    """Upload a local file to S3."""
    await asyncio.to_thread(_upload_file, local_path, s3_key)


def _upload_file(local_path: Path, s3_key: str) -> None:
    client = get_s3_client()
    client.upload_file(str(local_path), settings.s3_bucket, s3_key)


async def delete_file(s3_key: str) -> None:
    """Delete an object from S3."""
    await asyncio.to_thread(_delete_file, s3_key)


def _delete_file(s3_key: str) -> None:
    client = get_s3_client()
    client.delete_object(Bucket=settings.s3_bucket, Key=s3_key)


def build_public_url(s3_key: str) -> str:
    """Return the public URL for an S3 object key."""
    return f"{settings.s3_public_url.rstrip('/')}/{s3_key.lstrip('/')}"


def build_s3_key(plugin, version: str, source_type: str, commit_sha: str | None = None) -> str:
    """Build the S3 object key for a plugin zip package."""
    short = commit_sha[:7] if commit_sha else source_type
    filename = f"{plugin.plugin_key}-{version}-{short}.zip"
    author = plugin.author or settings.s3_unknown_author
    prefix = settings.s3_plugins_prefix.strip("/")
    return f"{prefix}/{author}/{plugin.plugin_key}/{version}/{filename}"
