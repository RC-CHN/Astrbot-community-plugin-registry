"""VirusTotal scan provider."""

from __future__ import annotations

import hashlib
import tempfile
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from ...models import PluginVersion
from ..runtime_config import runtime_virustotal_config
from ..s3_service import download_file
from .base import ScanOutcome, ScanProvider

VIRUSTOTAL_API_BASE_URL = "https://www.virustotal.com/api/v3"


class VirusTotalProvider(ScanProvider):
    name = "virustotal"
    label = "VirusTotal"
    legacy_public = True

    async def load_config(self, db: AsyncSession) -> dict[str, Any]:
        return await runtime_virustotal_config(db)

    def is_configured(self, config: dict[str, Any]) -> bool:
        return bool(config.get("api_key"))

    async def scan(
        self,
        version: PluginVersion,
        config: dict[str, Any],
        local_path: Path | None,
    ) -> ScanOutcome:
        return await scan_virustotal_for_version(version, config, local_path)


async def scan_virustotal_for_version(
    version: PluginVersion,
    vt_config: dict[str, Any],
    local_path: Path | None,
) -> ScanOutcome:
    if local_path is not None:
        return await scan_virustotal(local_path, vt_config)

    if not version.s3_key:
        return ScanOutcome(False, "VirusTotal scan failed: version artifact is missing", "error")

    with tempfile.TemporaryDirectory() as tmp:
        artifact_path = Path(tmp) / f"{version.id}.zip"
        try:
            await download_file(version.s3_key, artifact_path)
        except Exception as exc:
            return ScanOutcome(False, f"VirusTotal scan failed: could not download artifact: {exc}", "error")
        return await scan_virustotal(artifact_path, vt_config)


async def scan_virustotal(local_path: Path, vt_config: dict[str, Any]) -> ScanOutcome:
    max_direct_upload_bytes = int(vt_config["max_direct_upload_bytes"])
    file_size = local_path.stat().st_size
    if max_direct_upload_bytes > 0 and file_size > max_direct_upload_bytes:
        return ScanOutcome(
            False,
            "VirusTotal scan failed: file exceeds direct upload limit "
            f"({file_size} > {max_direct_upload_bytes} bytes)",
            "error",
        )

    headers = {"x-apikey": str(vt_config["api_key"])}
    timeout = max(1, int(vt_config["timeout_seconds"]))
    max_wait_seconds = max(1, int(vt_config["max_wait_seconds"]))

    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            file_sha256 = sha256_file(local_path)
            existing_stats = await get_virustotal_file_report(client, headers, file_sha256)
            if existing_stats is not None:
                return format_virustotal_result(existing_stats, f"file:{file_sha256}")

            try:
                analysis_id = await upload_to_virustotal(client, headers, local_path)
            except httpx.HTTPStatusError as exc:
                if exc.response.status_code != 409:
                    raise
                existing_stats = await get_virustotal_file_report(client, headers, file_sha256)
                if existing_stats is not None:
                    return format_virustotal_result(existing_stats, f"file:{file_sha256}")
                raise

            now = datetime.now(UTC)
            deadline = now + timedelta(seconds=max_wait_seconds)
            next_poll_at = min(
                now + timedelta(seconds=next_virustotal_delay(vt_config, 0)),
                deadline,
            )
            return ScanOutcome(
                None,
                "VirusTotal analysis pending: "
                f"analysis_id={analysis_id}, next_poll_at={next_poll_at.isoformat()}, "
                f"deadline_at={deadline.isoformat()}",
                "pending",
                virustotal_analysis_id=analysis_id,
                virustotal_file_sha256=file_sha256,
                virustotal_submitted_at=now,
                virustotal_deadline_at=deadline,
                virustotal_next_poll_at=next_poll_at,
                virustotal_poll_attempts=0,
            )
    except httpx.HTTPStatusError as exc:
        return ScanOutcome(False, f"VirusTotal scan failed: HTTP {exc.response.status_code}", "error")
    except httpx.HTTPError as exc:
        return ScanOutcome(False, f"VirusTotal scan failed: {exc}", "error")
    except (KeyError, TypeError, ValueError) as exc:
        return ScanOutcome(False, f"VirusTotal scan failed: invalid response: {exc}", "error")


async def poll_virustotal_analysis_once(analysis_id: str, vt_config: dict[str, Any]) -> ScanOutcome:
    headers = {"x-apikey": str(vt_config["api_key"])}
    timeout = max(1, int(vt_config["timeout_seconds"]))
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.get(
                f"{VIRUSTOTAL_API_BASE_URL}/analyses/{analysis_id}",
                headers=headers,
            )
            response.raise_for_status()
            data = response.json().get("data") or {}
            attributes = data.get("attributes") or {}
            status = str(attributes.get("status") or "unknown")
            if status == "completed":
                return format_virustotal_result(attributes.get("stats") or {}, analysis_id)
            return ScanOutcome(
                None,
                f"VirusTotal analysis pending: status={status}, analysis_id={analysis_id}",
                "pending",
                virustotal_analysis_id=analysis_id,
            )
    except httpx.HTTPStatusError as exc:
        return ScanOutcome(False, f"VirusTotal scan failed: HTTP {exc.response.status_code}", "error")
    except httpx.HTTPError as exc:
        return ScanOutcome(False, f"VirusTotal scan failed: {exc}", "error")
    except (KeyError, TypeError, ValueError) as exc:
        return ScanOutcome(False, f"VirusTotal scan failed: invalid response: {exc}", "error")


def next_virustotal_delay(config: dict[str, Any], attempts: int) -> int:
    base = max(1, int(config["poll_interval_seconds"]))
    max_interval = max(base, int(config["max_poll_interval_seconds"]))
    return min(base * (2 ** max(attempts, 0)), max_interval)


def virustotal_timeout_outcome(
    *,
    analysis_id: str,
    attempts: int,
    max_wait_seconds: int,
) -> ScanOutcome:
    return ScanOutcome(
        False,
        "VirusTotal scan timed out: analysis did not complete "
        f"within {max_wait_seconds} seconds after {attempts} polls, analysis_id={analysis_id}",
        "error",
        virustotal_analysis_id=analysis_id,
        virustotal_poll_attempts=attempts,
    )


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as artifact:
        for chunk in iter(lambda: artifact.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


async def get_virustotal_file_report(
    client: httpx.AsyncClient,
    headers: dict[str, str],
    file_sha256: str,
) -> dict[str, Any] | None:
    response = await client.get(
        f"{VIRUSTOTAL_API_BASE_URL}/files/{file_sha256}",
        headers=headers,
    )
    if response.status_code == 404:
        return None
    response.raise_for_status()
    data = response.json().get("data") or {}
    attributes = data.get("attributes") or {}
    stats = attributes.get("last_analysis_stats")
    if not isinstance(stats, dict):
        return None
    return stats


async def upload_to_virustotal(
    client: httpx.AsyncClient,
    headers: dict[str, str],
    local_path: Path,
) -> str:
    with open(local_path, "rb") as artifact:
        response = await client.post(
            f"{VIRUSTOTAL_API_BASE_URL}/files",
            headers=headers,
            files={"file": (local_path.name, artifact, "application/zip")},
        )
    response.raise_for_status()
    data = response.json()
    return str(data["data"]["id"])


def format_virustotal_result(stats: dict[str, Any], analysis_id: str) -> ScanOutcome:
    malicious = int(stats.get("malicious") or 0)
    suspicious = int(stats.get("suspicious") or 0)
    harmless = int(stats.get("harmless") or 0)
    undetected = int(stats.get("undetected") or 0)
    passed = malicious == 0 and suspicious == 0
    status = "passed" if passed else "failed"
    message = (
        f"VirusTotal {status}: malicious={malicious}, suspicious={suspicious}, "
        f"harmless={harmless}, undetected={undetected}, analysis_id={analysis_id}"
    )
    return ScanOutcome(passed, message, "real", virustotal_analysis_id=analysis_id)
