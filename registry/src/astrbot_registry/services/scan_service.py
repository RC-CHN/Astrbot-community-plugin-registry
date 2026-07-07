"""VirusTotal and LLM security scanning."""

from __future__ import annotations

import asyncio
import hashlib
import json
import tempfile
import uuid
import zipfile
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import PluginVersion, SecurityScan
from .runtime_config import runtime_llm_agent_config, runtime_scan_defaults, runtime_virustotal_config
from .s3_service import download_file
from .task_queue import enqueue_task

VIRUSTOTAL_API_BASE_URL = "https://www.virustotal.com/api/v3"
SCAN_PROVIDERS = {"virustotal", "llm_agent"}
SCAN_PROVIDER_ORDER = ("virustotal", "llm_agent")
LLM_RISK_FAIL_LEVELS = {"high", "critical"}
LLM_RELEVANT_SUFFIXES = {
    ".py",
    ".yaml",
    ".yml",
    ".toml",
    ".json",
    ".txt",
    ".md",
}
LLM_RELEVANT_NAMES = {
    "metadata.yaml",
    "metadata.yml",
    "requirements.txt",
    "pyproject.toml",
    "config.yaml",
    "config.yml",
}
LLM_SUSPICIOUS_TERMS = (
    "eval(",
    "exec(",
    "subprocess",
    "os.system",
    "socket",
    "requests.",
    "httpx.",
    "urllib",
    "base64",
    "pickle",
    "token",
    "cookie",
    "password",
    "secret",
    "api_key",
    "open(",
    "shutil",
)


@dataclass(frozen=True)
class ScanOutcome:
    passed: bool | None
    message: str
    mode: str
    virustotal_analysis_id: str | None = None
    virustotal_file_sha256: str | None = None
    virustotal_submitted_at: datetime | None = None
    virustotal_deadline_at: datetime | None = None
    virustotal_next_poll_at: datetime | None = None
    virustotal_poll_attempts: int | None = None


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
    selected = _normalize_providers(providers)
    version, scan = await _get_or_create_scan(db, version_id)

    if _can_mark_build_scanning(version):
        version.build_status = "scanning"
        await db.commit()

    defaults = await runtime_scan_defaults(db)
    vt_config = await runtime_virustotal_config(db) if "virustotal" in selected else None
    llm_config = await runtime_llm_agent_config(db) if "llm_agent" in selected else None
    outcomes = await _scan_selected_providers(
        version,
        selected,
        defaults,
        vt_config=vt_config,
        llm_config=llm_config,
        local_path=local_path,
    )
    virustotal_poll_delay: float | None = None
    for provider, outcome in outcomes.items():
        _set_provider_result(scan, provider, outcome.passed, outcome.message, outcome.mode)
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
    version: PluginVersion,
    selected: set[str],
    defaults: dict[str, Any],
    *,
    vt_config: dict[str, Any] | None,
    llm_config: dict[str, Any] | None,
    local_path: Path | None,
) -> dict[str, ScanOutcome]:
    outcomes: dict[str, ScanOutcome] = {}
    tasks: dict[str, asyncio.Task[ScanOutcome]] = {}

    for provider in SCAN_PROVIDER_ORDER:
        if provider not in selected:
            continue
        if provider == "virustotal":
            if vt_config and vt_config.get("api_key"):
                tasks[provider] = asyncio.create_task(
                    _scan_virustotal_for_version(version, vt_config, local_path)
                )
            else:
                outcomes[provider] = ScanOutcome(
                    defaults["pass_when_unconfigured"],
                    defaults["message"],
                    "skipped",
                )
        elif provider == "llm_agent":
            if llm_config and _llm_configured(llm_config):
                tasks[provider] = asyncio.create_task(
                    _scan_llm_for_version(version, llm_config, local_path)
                )
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
    for provider in _normalize_providers(providers):
        _set_provider_result(
            scan,
            provider,
            defaults["pass_when_unconfigured"],
            "Manually skipped",
            "skipped",
        )
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


def _next_virustotal_delay(config: dict[str, Any], attempts: int) -> int:
    base = max(1, int(config["poll_interval_seconds"]))
    max_interval = max(base, int(config["max_poll_interval_seconds"]))
    return min(base * (2 ** max(attempts, 0)), max_interval)


def _virustotal_timeout_outcome(
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


async def poll_virustotal_analysis(db: AsyncSession, version_id: uuid.UUID) -> SecurityScan:
    version, scan = await _get_or_create_scan(db, version_id)
    analysis_id = scan.virustotal_analysis_id
    if not analysis_id or scan.virustotal_mode != "pending":
        return scan

    config = await runtime_virustotal_config(db)
    if not config.get("api_key"):
        defaults = await runtime_scan_defaults(db)
        _set_provider_result(scan, "virustotal", defaults["pass_when_unconfigured"], defaults["message"], "skipped")
        _clear_virustotal_tracking(scan)
        scan.scanned_at = datetime.now(UTC)
        if version.s3_key and version.download_url:
            version.build_status = "success"
        await db.commit()
        await db.refresh(scan)
        await _refresh_registry_cache(db)
        return scan

    now = datetime.now(UTC)
    max_wait_seconds = max(1, int(config["max_wait_seconds"]))
    deadline = _aware(scan.virustotal_deadline_at) or now + timedelta(seconds=max_wait_seconds)
    if now >= deadline:
        outcome = _virustotal_timeout_outcome(
            analysis_id=analysis_id,
            attempts=scan.virustotal_poll_attempts,
            max_wait_seconds=max_wait_seconds,
        )
        _set_provider_result(scan, "virustotal", outcome.passed, outcome.message, outcome.mode)
        _apply_virustotal_tracking(scan, outcome)
        scan.scanned_at = now
        if version.s3_key and version.download_url:
            version.build_status = "success"
        await db.commit()
        await db.refresh(scan)
        await _refresh_registry_cache(db)
        return scan

    outcome = await _poll_virustotal_analysis(analysis_id, config)
    if outcome.mode == "pending":
        attempts = scan.virustotal_poll_attempts + 1
        max_attempts = max(1, int(config["max_poll_attempts"]))
        if attempts >= max_attempts:
            outcome = _virustotal_timeout_outcome(
                analysis_id=analysis_id,
                attempts=attempts,
                max_wait_seconds=max_wait_seconds,
            )
        else:
            delay = _next_virustotal_delay(config, attempts)
            next_poll_at = min(now + timedelta(seconds=delay), deadline)
            outcome = ScanOutcome(
                None,
                "VirusTotal analysis pending: "
                f"analysis_id={analysis_id}, attempt={attempts}, "
                f"next_poll_at={next_poll_at.isoformat()}, deadline_at={deadline.isoformat()}",
                "pending",
                virustotal_analysis_id=analysis_id,
                virustotal_file_sha256=scan.virustotal_file_sha256,
                virustotal_submitted_at=_aware(scan.virustotal_submitted_at),
                virustotal_deadline_at=deadline,
                virustotal_next_poll_at=next_poll_at,
                virustotal_poll_attempts=attempts,
            )

    _set_provider_result(scan, "virustotal", outcome.passed, outcome.message, outcome.mode)
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
    return scan


async def _refresh_registry_cache(db: AsyncSession) -> None:
    from ..services.registry_service import refresh_cache

    await refresh_cache(db)


def _llm_configured(config: dict[str, Any]) -> bool:
    return bool(config.get("enabled") and config.get("base_url") and config.get("model") and config.get("api_key"))


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


async def _scan_llm_for_version(
    version: PluginVersion,
    config: dict[str, Any],
    local_path: Path | None,
) -> ScanOutcome:
    if local_path is not None:
        return await _scan_llm(local_path, config)

    if not version.s3_key:
        return ScanOutcome(False, "LLM scan failed: version artifact is missing", "error")

    with tempfile.TemporaryDirectory() as tmp:
        artifact_path = Path(tmp) / f"{version.id}.zip"
        try:
            await download_file(version.s3_key, artifact_path)
        except Exception as exc:
            return ScanOutcome(False, f"LLM scan failed: could not download artifact: {exc}", "error")
        return await _scan_llm(artifact_path, config)


async def _scan_llm(local_path: Path, config: dict[str, Any]) -> ScanOutcome:
    try:
        context, truncated = _build_llm_context(local_path, int(config["max_context_chars"]))
        response = await _call_llm_agent(context, truncated, config)
        result = _parse_llm_response(response)
    except (OSError, zipfile.BadZipFile, KeyError, TypeError, ValueError) as exc:
        return ScanOutcome(False, f"LLM scan failed: {exc}", "error")
    except httpx.HTTPStatusError as exc:
        return ScanOutcome(False, f"LLM scan failed: HTTP {exc.response.status_code}", "error")
    except httpx.HTTPError as exc:
        return ScanOutcome(False, f"LLM scan failed: {exc}", "error")

    risk_level = str(result.get("risk_level") or "unknown").lower()
    passed = bool(result.get("pass")) and risk_level not in LLM_RISK_FAIL_LEVELS
    summary = str(result.get("summary") or "").strip()
    findings = result.get("findings") if isinstance(result.get("findings"), list) else []
    message = json.dumps(
        {
            "pass": passed,
            "risk_level": risk_level,
            "summary": summary,
            "findings": findings[:10],
            "context_truncated": truncated,
            "model": config["model"],
        },
        ensure_ascii=False,
        separators=(",", ":"),
    )
    return ScanOutcome(passed, message, "real")


def _build_llm_context(local_path: Path, max_chars: int) -> tuple[str, bool]:
    max_chars = max(1000, max_chars)
    sections: list[str] = []
    total_files = 0
    included_files = 0
    skipped_files = 0
    with zipfile.ZipFile(local_path) as zf:
        infos = [info for info in zf.infolist() if not info.is_dir()]
        total_files = len(infos)
        sections.append(f"Archive: {local_path.name}")
        sections.append(f"Total files: {total_files}")
        for info in infos:
            path = info.filename
            name = Path(path).name.lower()
            suffix = Path(path).suffix.lower()
            should_include = (
                name in LLM_RELEVANT_NAMES
                or suffix in LLM_RELEVANT_SUFFIXES
                or any(term in path.lower() for term in ("main", "plugin", "handler", "service"))
            )
            if not should_include:
                skipped_files += 1
                continue
            try:
                raw = zf.read(info, pwd=None)
                text = raw.decode("utf-8", errors="replace")
            except RuntimeError:
                skipped_files += 1
                continue
            included_files += 1
            sections.append(_format_llm_file_section(path, text))

        suspicious = _collect_suspicious_snippets(zf, infos)
        if suspicious:
            sections.append("Suspicious snippets:")
            sections.extend(suspicious)

    sections.insert(2, f"Included files: {included_files}; skipped binary/irrelevant files: {skipped_files}")
    context = "\n\n".join(sections)
    if len(context) <= max_chars:
        return context, False
    notice = (
        f"[Context truncated to {max_chars} characters from {len(context)} characters. "
        "Some files or snippets are omitted.]\n\n"
    )
    return notice + context[: max_chars - len(notice)], True


def _format_llm_file_section(path: str, text: str) -> str:
    max_file_chars = 4000
    truncated = len(text) > max_file_chars
    body = text[:max_file_chars]
    if truncated:
        body += "\n[File truncated]"
    return f"File: {path}\n```text\n{body}\n```"


def _collect_suspicious_snippets(
    zf: zipfile.ZipFile,
    infos: list[zipfile.ZipInfo],
) -> list[str]:
    snippets: list[str] = []
    for info in infos:
        if len(snippets) >= 20:
            break
        suffix = Path(info.filename).suffix.lower()
        if suffix not in LLM_RELEVANT_SUFFIXES:
            continue
        try:
            text = zf.read(info).decode("utf-8", errors="replace")
        except RuntimeError:
            continue
        lower = text.lower()
        if not any(term in lower for term in LLM_SUSPICIOUS_TERMS):
            continue
        lines = text.splitlines()
        matched: list[str] = []
        for idx, line in enumerate(lines):
            if any(term in line.lower() for term in LLM_SUSPICIOUS_TERMS):
                start = max(0, idx - 2)
                end = min(len(lines), idx + 3)
                matched.extend(f"{line_no + 1}: {lines[line_no]}" for line_no in range(start, end))
                break
        snippets.append(f"File: {info.filename}\n" + "\n".join(matched[:8]))
    return snippets


async def _call_llm_agent(context: str, truncated: bool, config: dict[str, Any]) -> str:
    base_url = str(config["base_url"]).rstrip("/")
    url = f"{base_url}/chat/completions"
    payload = {
        "model": config["model"],
        "temperature": 0,
        "response_format": {"type": "json_object"},
        "messages": [
            {
                "role": "system",
                "content": (
                    "You are a security reviewer for AstrBot plugin submissions. "
                    "Return exactly one strict JSON object and nothing else. Do not wrap it in markdown, "
                    "do not include code fences, comments, prose, or explanations outside the JSON object. "
                    "The JSON object must use keys: pass(boolean), risk_level("
                    "none|low|medium|high|critical), summary(string), findings(array). "
                    "Findings items should include severity, category, file, reason, recommendation. "
                    "Focus on malware, credential theft, unsafe code execution, hidden network behavior, "
                    "data exfiltration, and behavior inconsistent with metadata."
                ),
            },
            {
                "role": "user",
                "content": (
                    f"Context truncated: {truncated}. If truncated, mention that confidence is limited.\n\n"
                    f"{context}"
                ),
            },
        ],
    }
    headers = {"Authorization": f"Bearer {config['api_key']}", "Content-Type": "application/json"}
    async with httpx.AsyncClient(timeout=120) as client:
        response = await client.post(url, headers=headers, json=payload)
        response.raise_for_status()
    data = response.json()
    return str(data["choices"][0]["message"]["content"])


def _parse_llm_response(raw: str) -> dict[str, Any]:
    data = json.loads(_extract_json_object(raw))
    if not isinstance(data, dict):
        raise ValueError("LLM response is not a JSON object")
    if "pass" not in data or "risk_level" not in data:
        raise ValueError("LLM response is missing required keys")
    return data


def _extract_json_object(raw: str) -> str:
    text = raw.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].startswith("```"):
            lines = lines[:-1]
        text = "\n".join(lines).strip()
    if text.startswith("{") and text.endswith("}"):
        return text

    start = text.find("{")
    if start < 0:
        raise ValueError("LLM response does not contain a JSON object")

    depth = 0
    in_string = False
    escape = False
    for index in range(start, len(text)):
        char = text[index]
        if escape:
            escape = False
            continue
        if char == "\\":
            escape = True
            continue
        if char == '"':
            in_string = not in_string
            continue
        if in_string:
            continue
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return text[start : index + 1]

    raise ValueError("LLM response contains an incomplete JSON object")


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
    max_wait_seconds = max(1, int(vt_config["max_wait_seconds"]))

    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            file_sha256 = _sha256_file(local_path)
            existing_stats = await _get_virustotal_file_report(client, headers, file_sha256)
            if existing_stats is not None:
                return _format_virustotal_result(existing_stats, f"file:{file_sha256}")

            try:
                analysis_id = await _upload_to_virustotal(client, headers, local_path)
            except httpx.HTTPStatusError as exc:
                if exc.response.status_code != 409:
                    raise
                existing_stats = await _get_virustotal_file_report(client, headers, file_sha256)
                if existing_stats is not None:
                    return _format_virustotal_result(existing_stats, f"file:{file_sha256}")
                raise

            now = datetime.now(UTC)
            deadline = now + timedelta(seconds=max_wait_seconds)
            next_poll_at = min(
                now + timedelta(seconds=_next_virustotal_delay(vt_config, 0)),
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


async def _poll_virustotal_analysis(analysis_id: str, vt_config: dict[str, Any]) -> ScanOutcome:
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
                return _format_virustotal_result(attributes.get("stats") or {}, analysis_id)
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


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as artifact:
        for chunk in iter(lambda: artifact.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


async def _get_virustotal_file_report(
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
    return ScanOutcome(passed, message, "real", virustotal_analysis_id=analysis_id)
