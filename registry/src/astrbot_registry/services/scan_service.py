"""VirusTotal and LLM security scanning."""

from __future__ import annotations

import asyncio
import json
import tempfile
import uuid
import zipfile
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import PluginVersion, SecurityScan
from .runtime_config import runtime_llm_agent_config, runtime_scan_defaults, runtime_virustotal_config
from .s3_service import download_file

VIRUSTOTAL_API_BASE_URL = "https://www.virustotal.com/api/v3"
SCAN_PROVIDERS = {"virustotal", "llm_agent"}
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
        llm_config = await runtime_llm_agent_config(db)
        if _llm_configured(llm_config):
            llm_outcome = await _scan_llm_for_version(version, llm_config, local_path)
            scan.llm_agent_pass = llm_outcome.passed
            scan.llm_agent_msg = llm_outcome.message
            scan.llm_agent_mode = llm_outcome.mode
        else:
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
