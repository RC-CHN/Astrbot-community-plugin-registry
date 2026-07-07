"""LLM security-review scan provider."""

from __future__ import annotations

import json
import tempfile
import zipfile
from pathlib import Path
from typing import Any

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from ...models import PluginVersion
from ..runtime_config import runtime_llm_agent_config
from ..s3_service import download_file
from .base import ScanOutcome, ScanProvider

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
LLM_UNCERTAINTY_TERMS = (
    "truncated",
    "incomplete",
    "not visible",
    "not available",
    "cannot be ruled out",
    "could not be ruled out",
    "limited confidence",
    "full source",
    "hidden malicious behavior",
)
LLM_EXPLICIT_HIGH_RISK_TERMS = (
    "unknown domain",
    "untrusted domain",
    "third-party domain",
    "non-github domain",
    "download and execute",
    "downloads and executes",
    "downloads code",
    "remote code execution",
    "eval(",
    "exec(",
    "os.system",
    "subprocess",
    "pickle.loads",
    "base64.b64decode",
    "reverse shell",
    "backdoor",
    "steals",
    "exfiltrates",
    "sends credentials",
    "sends token",
    "credential theft is implemented",
)


class LLMAgentProvider(ScanProvider):
    name = "llm_agent"
    label = "LLM Agent"
    legacy_public = True

    async def load_config(self, db: AsyncSession) -> dict[str, Any]:
        return await runtime_llm_agent_config(db)

    def is_configured(self, config: dict[str, Any]) -> bool:
        return llm_configured(config)

    async def scan(
        self,
        version: PluginVersion,
        config: dict[str, Any],
        local_path: Path | None,
    ) -> ScanOutcome:
        return await scan_llm_for_version(version, config, local_path)


def llm_configured(config: dict[str, Any]) -> bool:
    return bool(config.get("base_url") and config.get("model") and config.get("api_key"))


async def scan_llm_for_version(
    version: PluginVersion,
    config: dict[str, Any],
    local_path: Path | None,
) -> ScanOutcome:
    if local_path is not None:
        return await scan_llm(local_path, config)

    if not version.s3_key:
        return ScanOutcome(False, "LLM scan failed: version artifact is missing", "error")

    with tempfile.TemporaryDirectory() as tmp:
        artifact_path = Path(tmp) / f"{version.id}.zip"
        try:
            await download_file(version.s3_key, artifact_path)
        except Exception as exc:
            return ScanOutcome(False, f"LLM scan failed: could not download artifact: {exc}", "error")
        return await scan_llm(artifact_path, config)


async def scan_llm(local_path: Path, config: dict[str, Any]) -> ScanOutcome:
    try:
        context, truncated = build_llm_context(local_path, int(config["max_context_chars"]))
        response = await call_llm_agent(context, truncated, config)
        result = normalize_llm_result(parse_llm_response(response))
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
            **({"normalization_note": result["normalization_note"]} if result.get("normalization_note") else {}),
        },
        ensure_ascii=False,
        separators=(",", ":"),
    )
    return ScanOutcome(passed, message, "real")


def normalize_llm_result(result: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(result)
    risk_level = str(normalized.get("risk_level") or "unknown").lower()
    if risk_level in LLM_RISK_FAIL_LEVELS and looks_uncertainty_only_high_risk(normalized):
        normalized["risk_level"] = "medium"
        normalized["pass"] = True
        normalized["normalization_note"] = (
            "High risk downgraded because the finding is based on incomplete context "
            "or uncertainty without explicit visible high-risk behavior."
        )
    elif risk_level not in LLM_RISK_FAIL_LEVELS:
        normalized["pass"] = True
    return normalized


def looks_uncertainty_only_high_risk(result: dict[str, Any]) -> bool:
    text = llm_result_text(result).lower()
    if not any(term in text for term in LLM_UNCERTAINTY_TERMS):
        return False
    return not any(term in text for term in LLM_EXPLICIT_HIGH_RISK_TERMS)


def llm_result_text(result: dict[str, Any]) -> str:
    parts = [str(result.get("summary") or "")]
    findings = result.get("findings")
    if isinstance(findings, list):
        for finding in findings:
            if isinstance(finding, dict):
                parts.extend(str(value) for value in finding.values())
            else:
                parts.append(str(finding))
    return "\n".join(parts)


def build_llm_context(local_path: Path, max_chars: int) -> tuple[str, bool]:
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
            sections.append(format_llm_file_section(path, text))

        suspicious = collect_suspicious_snippets(zf, infos)
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


def format_llm_file_section(path: str, text: str) -> str:
    max_file_chars = 4000
    truncated = len(text) > max_file_chars
    body = text[:max_file_chars]
    if truncated:
        body += "\n[File truncated]"
    return f"File: {path}\n```text\n{body}\n```"


def collect_suspicious_snippets(
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


async def call_llm_agent(context: str, truncated: bool, config: dict[str, Any]) -> str:
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
                    "data exfiltration, and behavior inconsistent with metadata. "
                    "Use pass=false only for high or critical risk with explicit evidence in visible code. "
                    "Do not assign high or critical risk only because the context is truncated, incomplete, "
                    "or because malicious behavior cannot be ruled out. Missing context is a confidence "
                    "limitation, not a high-risk finding by itself. Treat incomplete source, broad "
                    "recommendations, and speculative hidden behavior as low or medium unless visible code "
                    "shows a concrete dangerous action such as downloading or executing remote code, sending "
                    "credentials/tokens/data to an unknown or untrusted domain, obfuscation, a backdoor, "
                    "destructive filesystem actions, or explicit exfiltration."
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


def parse_llm_response(raw: str) -> dict[str, Any]:
    data = json.loads(extract_json_object(raw))
    if not isinstance(data, dict):
        raise ValueError("LLM response is not a JSON object")
    if "pass" not in data or "risk_level" not in data:
        raise ValueError("LLM response is missing required keys")
    return data


def extract_json_object(raw: str) -> str:
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
