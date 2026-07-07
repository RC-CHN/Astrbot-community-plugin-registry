"""Security scan orchestration."""

from __future__ import annotations

import asyncio
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import PluginVersion, ReviewProviderResult, SecurityScan
from .runtime_config import (
    runtime_scan_defaults,
    runtime_scan_enabled_providers,
    runtime_review_policy,
    runtime_virustotal_config,
)
from .scan_providers import ScanOutcome, get_scan_provider_registry
from .scan_providers.virustotal import (
    next_virustotal_delay,
    poll_virustotal_analysis_once,
    virustotal_timeout_outcome,
)
from .task_queue import enqueue_task

SCAN_PROVIDER_ORDER = get_scan_provider_registry().names
SCAN_PROVIDERS = set(SCAN_PROVIDER_ORDER)
LEGACY_PUBLIC_SCAN_PROVIDERS = get_scan_provider_registry().legacy_public_names


def scan_provider_results(version: PluginVersion) -> dict[str, dict[str, Any]]:
    """Return provider scan results keyed by provider, with legacy fallback."""
    provider_results = {
        result.provider: _provider_result_payload(result)
        for result in getattr(version, "provider_results", []) or []
        if result.kind == "scan"
    }
    scan = version.scan
    if scan:
        legacy_results = {
            "virustotal": {
                "pass": scan.virustotal_pass,
                "msg": scan.virustotal_msg,
                "mode": scan.virustotal_mode,
            },
            "llm_agent": {
                "pass": scan.llm_agent_pass,
                "msg": scan.llm_agent_msg,
                "mode": scan.llm_agent_mode,
            },
        }
        for provider, payload in legacy_results.items():
            provider_results.setdefault(provider, payload)
    return provider_results


def public_sec_scan(
    version: PluginVersion,
    *,
    coerce_unknown_to_false: bool = False,
) -> dict[str, dict[str, Any]]:
    """Format public sec_scan with known legacy keys first, then any extra providers."""
    results = scan_provider_results(version)
    output: dict[str, dict[str, Any]] = {}
    for provider in get_scan_provider_registry().legacy_public_names:
        if provider in results:
            output[provider] = _scan_payload_for_public(
                results[provider],
                coerce_unknown_to_false=coerce_unknown_to_false,
            )
    for provider, payload in results.items():
        if provider not in output and provider != "human":
            output[provider] = _scan_payload_for_public(
                payload,
                coerce_unknown_to_false=coerce_unknown_to_false,
            )
    return output


def version_scan_summary(version: PluginVersion) -> dict[str, Any] | None:
    results = scan_provider_results(version)
    if not results and not version.scan:
        return None
    output = public_sec_scan(version)
    scanned_at = None
    if version.scan and version.scan.scanned_at:
        scanned_at = version.scan.scanned_at.isoformat()
    provider_updated_at = [
        result.updated_at
        for result in getattr(version, "provider_results", []) or []
        if result.kind == "scan" and result.updated_at is not None
    ]
    if provider_updated_at:
        scanned_at = max(provider_updated_at).isoformat()
    output["scanned_at"] = scanned_at
    return output


def scan_providers_passed(version: PluginVersion, providers: tuple[str, ...] | None = None) -> bool:
    results = scan_provider_results(version)
    selected_results = (
        {provider: results.get(provider) for provider in providers}
        if providers is not None
        else results
    )
    if providers is not None and any(result is None for result in selected_results.values()):
        return False
    for result in selected_results.values():
        if not result:
            continue
        if result.get("mode") == "skipped":
            continue
        if result.get("mode") in {"pending", "error"}:
            return False
        if result.get("pass") is False:
            return False
        if result.get("pass") is None:
            return False
    return True


def _provider_result_payload(result: ReviewProviderResult) -> dict[str, Any]:
    return {
        "pass": result.passed,
        "msg": result.message,
        "mode": result.mode,
    }


def _scan_payload_for_public(
    payload: dict[str, Any],
    *,
    coerce_unknown_to_false: bool,
) -> dict[str, Any]:
    output = dict(payload)
    if coerce_unknown_to_false:
        output["pass"] = bool(output.get("pass"))
    return output


async def scan_version(
    db: AsyncSession,
    version_id: uuid.UUID,
    *,
    local_path: Path | None = None,
    providers: list[str] | None = None,
) -> SecurityScan:
    """Run security scans on a plugin version.

    If VirusTotal is configured, the packaged zip is uploaded directly and a
    follow-up polling task is queued until the remote analysis completes.
    Without a configured scanner, the development default is used so local
    workflows can still progress.
    """
    selected = await _selected_scan_providers(db, providers)
    version, scan = await _get_or_create_scan(db, version_id)

    if _can_mark_build_scanning(version):
        version.build_status = "scanning"
        await db.commit()

    defaults = await runtime_scan_defaults(db)
    outcomes = await _scan_selected_providers(
        db,
        version,
        selected,
        defaults,
        local_path=local_path,
    )
    virustotal_poll_delay: float | None = None
    for provider, outcome in outcomes.items():
        provider_result = await _get_or_create_provider_result(db, version.id, provider)
        if provider in get_scan_provider_registry().legacy_public_names:
            _set_provider_result(scan, provider, outcome.passed, outcome.message, outcome.mode)
        _set_review_provider_result(provider_result, provider, outcome)
        if provider == "virustotal":
            _apply_virustotal_tracking(scan, outcome)
            if outcome.virustotal_analysis_id and outcome.virustotal_next_poll_at:
                virustotal_poll_delay = _seconds_until(outcome.virustotal_next_poll_at)
    scan.scanned_at = datetime.now(UTC)
    if version.s3_key and version.download_url:
        version.build_status = "scanning" if any(outcome.mode == "pending" for outcome in outcomes.values()) else "success"
    await db.commit()
    await db.refresh(scan)
    if virustotal_poll_delay is not None:
        await enqueue_task(
            "virustotal_poll",
            {"version_id": str(version.id)},
            db,
            delay_seconds=virustotal_poll_delay,
        )
    from ..services.registry_service import refresh_cache

    await refresh_cache(db)
    if virustotal_poll_delay is None:
        await _try_auto_publish_after_scan(db, version.id)
    return scan


async def mark_scan_pending(
    db: AsyncSession,
    version_id: uuid.UUID,
    *,
    providers: list[str] | None = None,
) -> SecurityScan:
    version, scan = await _get_or_create_scan(db, version_id)
    for provider in await _selected_scan_providers(db, providers):
        provider_result = await _get_or_create_provider_result(db, version.id, provider)
        if provider in get_scan_provider_registry().legacy_public_names:
            _set_provider_result(scan, provider, None, "Scan queued", "pending")
        _set_review_provider_result(provider_result, provider, ScanOutcome(None, "Scan queued", "pending"))
        if provider == "virustotal":
            _clear_virustotal_tracking(scan)
    scan.scanned_at = datetime.now(UTC)
    if _can_mark_build_scanning(version):
        version.build_status = "scanning"
    await db.commit()
    await db.refresh(scan)

    from ..services.registry_service import refresh_cache

    await refresh_cache(db)
    return scan


def _can_mark_build_scanning(version: PluginVersion) -> bool:
    """Avoid violating the latest-version invariant while rescanning published versions."""
    if not (version.s3_key and version.download_url):
        return False
    return not (version.is_latest and version.version_status == "active")


async def _scan_selected_providers(
    db: AsyncSession,
    version: PluginVersion,
    selected: list[str],
    defaults: dict[str, Any],
    *,
    local_path: Path | None,
) -> dict[str, ScanOutcome]:
    outcomes: dict[str, ScanOutcome] = {}
    tasks: dict[str, asyncio.Task[ScanOutcome]] = {}
    registry = get_scan_provider_registry()

    for provider in registry.names:
        if provider not in selected:
            continue
        definition = registry.get(provider)
        if definition is None:
            continue
        config = await definition.load_config(db)
        if definition.is_configured(config):
            tasks[provider] = asyncio.create_task(definition.scan(version, config, local_path))
        else:
            outcomes[provider] = ScanOutcome(
                defaults["pass_when_unconfigured"],
                defaults["message"],
                "skipped",
            )

    if tasks:
        providers = list(tasks)
        results = await asyncio.gather(*(tasks[provider] for provider in providers))
        outcomes.update(dict(zip(providers, results, strict=True)))

    return outcomes


async def mark_scan_skipped(
    db: AsyncSession,
    version_id: uuid.UUID,
    *,
    providers: list[str] | None = None,
) -> SecurityScan:
    version, scan = await _get_or_create_scan(db, version_id)
    defaults = await runtime_scan_defaults(db)
    for provider in await _selected_scan_providers(db, providers):
        provider_result = await _get_or_create_provider_result(db, version.id, provider)
        outcome = ScanOutcome(
            defaults["pass_when_unconfigured"],
            "Manually skipped",
            "skipped",
        )
        if provider in get_scan_provider_registry().legacy_public_names:
            _set_provider_result(
                scan,
                provider,
                outcome.passed,
                outcome.message,
                outcome.mode,
            )
        _set_review_provider_result(provider_result, provider, outcome)
        if provider == "virustotal":
            _clear_virustotal_tracking(scan)
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


async def _get_or_create_provider_result(
    db: AsyncSession,
    version_id: uuid.UUID,
    provider: str,
    *,
    kind: str = "scan",
) -> ReviewProviderResult:
    result = await db.execute(
        select(ReviewProviderResult)
        .where(ReviewProviderResult.version_id == version_id)
        .where(ReviewProviderResult.provider == provider)
    )
    provider_result = result.scalar_one_or_none()
    if provider_result is None:
        provider_result = ReviewProviderResult(
            version_id=version_id,
            provider=provider,
            kind=kind,
        )
        db.add(provider_result)
    return provider_result


async def _selected_scan_providers(db: AsyncSession, providers: list[str] | None) -> list[str]:
    registry = get_scan_provider_registry()
    if providers is None:
        return registry.validate(await runtime_scan_enabled_providers(db))
    return registry.validate(providers)


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


def _set_review_provider_result(
    result: ReviewProviderResult,
    provider: str,
    outcome: ScanOutcome,
) -> None:
    result.provider = provider
    result.kind = "scan"
    result.passed = outcome.passed
    result.message = outcome.message
    result.mode = outcome.mode
    result.completed_at = datetime.now(UTC) if outcome.mode != "pending" else None

    if provider == "virustotal":
        result.external_id = outcome.virustotal_analysis_id
        result.submitted_at = outcome.virustotal_submitted_at
        result.deadline_at = outcome.virustotal_deadline_at
        result.next_poll_at = outcome.virustotal_next_poll_at if outcome.mode == "pending" else None
        if outcome.virustotal_poll_attempts is not None:
            result.attempts = outcome.virustotal_poll_attempts
        result.details_json = (
            {"file_sha256": outcome.virustotal_file_sha256}
            if outcome.virustotal_file_sha256
            else result.details_json
        )
        return

    result.external_id = None
    result.submitted_at = None
    result.deadline_at = None
    result.next_poll_at = None
    result.attempts = 0


def _apply_virustotal_tracking(scan: SecurityScan, outcome: ScanOutcome) -> None:
    if outcome.virustotal_analysis_id:
        scan.virustotal_analysis_id = outcome.virustotal_analysis_id
    if outcome.virustotal_file_sha256:
        scan.virustotal_file_sha256 = outcome.virustotal_file_sha256
    if outcome.virustotal_submitted_at:
        scan.virustotal_submitted_at = outcome.virustotal_submitted_at
    if outcome.virustotal_deadline_at:
        scan.virustotal_deadline_at = outcome.virustotal_deadline_at
    if outcome.virustotal_poll_attempts is not None:
        scan.virustotal_poll_attempts = outcome.virustotal_poll_attempts

    if outcome.mode == "pending":
        scan.virustotal_next_poll_at = outcome.virustotal_next_poll_at
    else:
        scan.virustotal_next_poll_at = None


def _clear_virustotal_tracking(scan: SecurityScan) -> None:
    scan.virustotal_analysis_id = None
    scan.virustotal_file_sha256 = None
    scan.virustotal_submitted_at = None
    scan.virustotal_deadline_at = None
    scan.virustotal_next_poll_at = None
    scan.virustotal_poll_attempts = 0


def _provider_file_sha256(result: ReviewProviderResult) -> str | None:
    details = result.details_json
    if not isinstance(details, dict):
        return None
    value = details.get("file_sha256")
    return str(value) if value else None


def _aware(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value


def _seconds_until(value: datetime) -> float:
    aware_value = _aware(value)
    if aware_value is None:
        return 0.0
    return max(0.0, (aware_value - datetime.now(UTC)).total_seconds())


async def poll_virustotal_analysis(db: AsyncSession, version_id: uuid.UUID) -> SecurityScan:
    version, scan = await _get_or_create_scan(db, version_id)
    provider_result = await _get_or_create_provider_result(db, version.id, "virustotal")
    analysis_id = provider_result.external_id or scan.virustotal_analysis_id
    mode = provider_result.mode or scan.virustotal_mode
    if not analysis_id or mode != "pending":
        return scan

    config = await runtime_virustotal_config(db)
    if not config.get("api_key"):
        defaults = await runtime_scan_defaults(db)
        outcome = ScanOutcome(
            defaults["pass_when_unconfigured"],
            defaults["message"],
            "skipped",
            virustotal_analysis_id=analysis_id,
        )
        _set_provider_result(scan, "virustotal", outcome.passed, outcome.message, outcome.mode)
        _set_review_provider_result(provider_result, "virustotal", outcome)
        _clear_virustotal_tracking(scan)
        scan.scanned_at = datetime.now(UTC)
        if version.s3_key and version.download_url:
            version.build_status = "success"
        await db.commit()
        await db.refresh(scan)
        await _refresh_registry_cache(db)
        await _try_auto_publish_after_scan(db, version.id)
        return scan

    now = datetime.now(UTC)
    max_wait_seconds = max(1, int(config["max_wait_seconds"]))
    deadline = _aware(provider_result.deadline_at) or _aware(scan.virustotal_deadline_at)
    deadline = deadline or now + timedelta(seconds=max_wait_seconds)
    attempts_so_far = max(provider_result.attempts or 0, scan.virustotal_poll_attempts or 0)
    if now >= deadline:
        outcome = virustotal_timeout_outcome(
            analysis_id=analysis_id,
            attempts=attempts_so_far,
            max_wait_seconds=max_wait_seconds,
        )
        _set_provider_result(scan, "virustotal", outcome.passed, outcome.message, outcome.mode)
        _set_review_provider_result(provider_result, "virustotal", outcome)
        _apply_virustotal_tracking(scan, outcome)
        scan.scanned_at = now
        if version.s3_key and version.download_url:
            version.build_status = "success"
        await db.commit()
        await db.refresh(scan)
        await _refresh_registry_cache(db)
        await _try_auto_publish_after_scan(db, version.id)
        return scan

    outcome = await poll_virustotal_analysis_once(analysis_id, config)
    if outcome.mode == "pending":
        attempts = attempts_so_far + 1
        max_attempts = max(1, int(config["max_poll_attempts"]))
        if attempts >= max_attempts:
            outcome = virustotal_timeout_outcome(
                analysis_id=analysis_id,
                attempts=attempts,
                max_wait_seconds=max_wait_seconds,
            )
        else:
            delay = next_virustotal_delay(config, attempts)
            next_poll_at = min(now + timedelta(seconds=delay), deadline)
            outcome = ScanOutcome(
                None,
                "VirusTotal analysis pending: "
                f"analysis_id={analysis_id}, attempt={attempts}, "
                f"next_poll_at={next_poll_at.isoformat()}, deadline_at={deadline.isoformat()}",
                "pending",
                virustotal_analysis_id=analysis_id,
                virustotal_file_sha256=_provider_file_sha256(provider_result) or scan.virustotal_file_sha256,
                virustotal_submitted_at=_aware(provider_result.submitted_at)
                or _aware(scan.virustotal_submitted_at),
                virustotal_deadline_at=deadline,
                virustotal_next_poll_at=next_poll_at,
                virustotal_poll_attempts=attempts,
            )

    _set_provider_result(scan, "virustotal", outcome.passed, outcome.message, outcome.mode)
    _set_review_provider_result(provider_result, "virustotal", outcome)
    _apply_virustotal_tracking(scan, outcome)
    scan.scanned_at = datetime.now(UTC)
    if version.s3_key and version.download_url:
        version.build_status = "scanning" if outcome.mode == "pending" else "success"
    await db.commit()
    await db.refresh(scan)
    if outcome.mode == "pending" and outcome.virustotal_next_poll_at:
        await enqueue_task(
            "virustotal_poll",
            {"version_id": str(version.id)},
            db,
            delay_seconds=_seconds_until(outcome.virustotal_next_poll_at),
        )
    await _refresh_registry_cache(db)
    if outcome.mode != "pending":
        await _try_auto_publish_after_scan(db, version.id)
    return scan


async def _refresh_registry_cache(db: AsyncSession) -> None:
    from ..services.registry_service import refresh_cache

    await refresh_cache(db)


async def _try_auto_publish_after_scan(db: AsyncSession, version_id: uuid.UUID) -> bool:
    policy = await runtime_review_policy(db)
    if not policy["auto_publish"] or policy["require_human_review"]:
        return False

    version = await db.get(PluginVersion, version_id)
    if version is None:
        return False

    from ..services.errors import InvalidStateError, NotFoundError, ValidationError
    from ..services.plugin_service import publish_plugin_version

    try:
        await publish_plugin_version(
            db,
            version.plugin_id,
            version.id,
            review_status="skipped",
        )
    except (InvalidStateError, NotFoundError, ValidationError):
        return False
    return True
