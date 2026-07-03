"""VirusTotal and LLM security scanning."""

from __future__ import annotations

import asyncio
import tempfile
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import PluginVersion, SecurityScan
from .runtime_config import runtime_scan_defaults, runtime_virustotal_config
from .s3_service import download_file

VIRUSTOTAL_API_BASE_URL = "https://www.virustotal.com/api/v3"
SCAN_PROVIDERS = {"virustotal", "llm_agent"}


@dataclass(frozen=True)
class ScanOutcome:
    passed: bool | None
    message: str
    mode: str


async def scan_version(
    db: AsyncSession,
    version_id: uuid.UUID,
    *,
    local_path: Path | None = None,
    providers: list[str] | None = None,
) -> SecurityScan:
    """Run security scans on a plugin version.

    If VirusTotal is configured, the packaged zip is uploaded directly and the
    analysis is polled until completion. Without a configured scanner, the
    development default is used so local workflows can still progress.
    """
    selected = _normalize_providers(providers)
    version, scan = await _get_or_create_scan(db, version_id)

    if version.s3_key and version.download_url:
        version.build_status = "scanning"
        await db.commit()

    defaults = await runtime_scan_defaults(db)
    if "virustotal" in selected:
        vt_config = await runtime_virustotal_config(db)
        if vt_config["api_key"]:
            vt_outcome = await _scan_virustotal_for_version(
                version,
                vt_config,
                local_path,
            )
            scan.virustotal_pass = vt_outcome.passed
            scan.virustotal_msg = vt_outcome.message
            scan.virustotal_mode = vt_outcome.mode
        else:
            scan.virustotal_pass = defaults["pass_when_unconfigured"]
            scan.virustotal_msg = defaults["message"]
            scan.virustotal_mode = "skipped"
    if "llm_agent" in selected:
        scan.llm_agent_pass = defaults["pass_when_unconfigured"]
        scan.llm_agent_msg = defaults["message"]
        scan.llm_agent_mode = "skipped"
    scan.scanned_at = datetime.now(UTC)
    if version.s3_key and version.download_url:
        version.build_status = "success"
    await db.commit()
    await db.refresh(scan)
    from ..services.registry_service import refresh_cache

    await refresh_cache(db)
    return scan


async def mark_scan_pending(
    db: AsyncSession,
    version_id: uuid.UUID,
    *,
    providers: list[str] | None = None,
) -> SecurityScan:
    version, scan = await _get_or_create_scan(db, version_id)
    for provider in _normalize_providers(providers):
        _set_provider_result(scan, provider, None, "Scan queued", "pending")
    scan.scanned_at = datetime.now(UTC)
    if version.s3_key and version.download_url:
        version.build_status = "scanning"
    await db.commit()
    await db.refresh(scan)

    from ..services.registry_service import refresh_cache

    await refresh_cache(db)
    return scan


async def mark_scan_skipped(
    db: AsyncSession,
    version_id: uuid.UUID,
    *,
    providers: list[str] | None = None,
) -> SecurityScan:
    version, scan = await _get_or_create_scan(db, version_id)
    defaults = await runtime_scan_defaults(db)
    for provider in _normalize_providers(providers):
        _set_provider_result(
            scan,
            provider,
            defaults["pass_when_unconfigured"],
            "Manually skipped",
            "skipped",
        )
    scan.scanned_at = datetime.now(UTC)
    if version.s3_key and version.download_url:
        version.build_status = "success"
    await db.commit()
    await db.refresh(scan)

    from ..services.registry_service import refresh_cache

    await refresh_cache(db)
    return scan


async def _get_or_create_scan(
    db: AsyncSession,
    version_id: uuid.UUID,
) -> tuple[PluginVersion, SecurityScan]:
    version = await db.get(PluginVersion, version_id)
    if version is None:
        raise ValueError("Version not found")

    result = await db.execute(
        select(SecurityScan).where(SecurityScan.version_id == version.id)
    )
    scan = result.scalar_one_or_none()
    if scan is None:
        scan = SecurityScan(version_id=version.id)
        db.add(scan)
    return version, scan


def _normalize_providers(providers: list[str] | None) -> set[str]:
    if not providers:
        return set(SCAN_PROVIDERS)
    selected = set(providers)
    invalid = selected - SCAN_PROVIDERS
    if invalid:
        raise ValueError(f"Invalid scan providers: {', '.join(sorted(invalid))}")
    return selected


def _set_provider_result(
    scan: SecurityScan,
    provider: str,
    passed: bool | None,
    message: str,
    mode: str,
) -> None:
    if provider == "virustotal":
        scan.virustotal_pass = passed
        scan.virustotal_msg = message
        scan.virustotal_mode = mode
        return
    if provider == "llm_agent":
        scan.llm_agent_pass = passed
        scan.llm_agent_msg = message
        scan.llm_agent_mode = mode
        return
    raise ValueError(f"Invalid scan provider: {provider}")


async def _scan_virustotal_for_version(
    version: PluginVersion,
    vt_config: dict[str, Any],
    local_path: Path | None,
) -> ScanOutcome:
    if local_path is not None:
        return await _scan_virustotal(local_path, vt_config)

    if not version.s3_key:
        return ScanOutcome(False, "VirusTotal scan failed: version artifact is missing", "error")

    with tempfile.TemporaryDirectory() as tmp:
        artifact_path = Path(tmp) / f"{version.id}.zip"
        try:
            await download_file(version.s3_key, artifact_path)
        except Exception as exc:
            return ScanOutcome(False, f"VirusTotal scan failed: could not download artifact: {exc}", "error")
        return await _scan_virustotal(artifact_path, vt_config)


async def _scan_virustotal(local_path: Path, vt_config: dict[str, Any]) -> ScanOutcome:
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
    poll_interval = max(1, int(vt_config["poll_interval_seconds"]))
    max_poll_attempts = max(1, int(vt_config["max_poll_attempts"]))

    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            analysis_id = await _upload_to_virustotal(client, headers, local_path)
            for _ in range(max_poll_attempts):
                response = await client.get(
                    f"{VIRUSTOTAL_API_BASE_URL}/analyses/{analysis_id}",
                    headers=headers,
                )
                response.raise_for_status()
                data = response.json().get("data") or {}
                attributes = data.get("attributes") or {}
                if attributes.get("status") == "completed":
                    return _format_virustotal_result(attributes.get("stats") or {}, analysis_id)
                await asyncio.sleep(poll_interval)
    except httpx.HTTPStatusError as exc:
        return ScanOutcome(False, f"VirusTotal scan failed: HTTP {exc.response.status_code}", "error")
    except httpx.HTTPError as exc:
        return ScanOutcome(False, f"VirusTotal scan failed: {exc}", "error")
    except (KeyError, TypeError, ValueError) as exc:
        return ScanOutcome(False, f"VirusTotal scan failed: invalid response: {exc}", "error")

    return ScanOutcome(
        False,
        f"VirusTotal scan timed out: analysis did not complete after {max_poll_attempts} polls",
        "error",
    )


async def _upload_to_virustotal(
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


def _format_virustotal_result(stats: dict[str, Any], analysis_id: str) -> ScanOutcome:
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
    return ScanOutcome(passed, message, "real")
