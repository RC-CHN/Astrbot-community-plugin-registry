import pytest

from astrbot_registry.services.scan_providers import (
    ScanOutcome,
    ScanProvider,
    ScanProviderRegistry,
    reset_scan_provider_registry,
    set_scan_provider_registry,
)
from astrbot_registry.services.scan_providers.clamav import format_clamav_reply
from astrbot_registry.services.scan_providers.llm_agent import (
    build_llm_context,
    parse_llm_response,
    scan_llm,
)
from astrbot_registry.services.scan_providers.virustotal import (
    format_virustotal_result,
    poll_virustotal_analysis_once,
    scan_virustotal,
)
from astrbot_registry.services.scan_service import (
    _can_mark_build_scanning,
    _scan_selected_providers,
    scan_providers_passed,
)
from astrbot_registry.models import PluginVersion, ReviewProviderResult


def test_format_virustotal_result_passes_clean_analysis() -> None:
    outcome = format_virustotal_result(
        {
            "malicious": 0,
            "suspicious": 0,
            "harmless": 3,
            "undetected": 62,
        },
        "analysis-id",
    )

    assert outcome.passed is True
    assert outcome.mode == "real"
    assert "VirusTotal passed" in outcome.message
    assert "malicious=0" in outcome.message
    assert "analysis_id=analysis-id" in outcome.message


def test_format_virustotal_result_fails_malicious_or_suspicious_analysis() -> None:
    outcome = format_virustotal_result(
        {
            "malicious": 1,
            "suspicious": 2,
            "harmless": 3,
            "undetected": 4,
        },
        "analysis-id",
    )

    assert outcome.passed is False
    assert outcome.mode == "real"
    assert "VirusTotal failed" in outcome.message
    assert "malicious=1" in outcome.message
    assert "suspicious=2" in outcome.message


def test_latest_active_version_is_not_marked_scanning() -> None:
    version = PluginVersion(
        s3_key="plugins/example.zip",
        download_url="https://example.test/plugin.zip",
        is_latest=True,
        version_status="active",
    )

    assert _can_mark_build_scanning(version) is False


def test_draft_version_can_be_marked_scanning() -> None:
    version = PluginVersion(
        s3_key="plugins/example.zip",
        download_url="https://example.test/plugin.zip",
        is_latest=False,
        version_status="draft",
    )

    assert _can_mark_build_scanning(version) is True


@pytest.mark.asyncio
async def test_selected_scan_providers_run_concurrently() -> None:
    import asyncio

    version = PluginVersion(
        s3_key="plugins/example.zip",
        download_url="https://example.test/plugin.zip",
    )
    vt_started = asyncio.Event()
    llm_started = asyncio.Event()

    class FakeProvider(ScanProvider):
        def __init__(self, name, message, started, peer_started):
            self.name = name
            self.label = name
            self.message = message
            self.started = started
            self.peer_started = peer_started

        async def load_config(self, db):
            return {"enabled": True}

        def is_configured(self, config):
            return True

        async def scan(self, version, config, local_path):
            self.started.set()
            await self.peer_started.wait()
            return ScanOutcome(True, self.message, "real")

    set_scan_provider_registry(
        ScanProviderRegistry(
            (
                FakeProvider("virustotal", "vt ok", vt_started, llm_started),
                FakeProvider("llm_agent", "llm ok", llm_started, vt_started),
            )
        )
    )
    try:
        outcomes = await asyncio.wait_for(
            _scan_selected_providers(
                None,  # type: ignore[arg-type]
                version,
                ["virustotal", "llm_agent"],
                {"pass_when_unconfigured": True, "message": "skipped"},
                local_path=None,
            ),
            timeout=1,
        )
    finally:
        reset_scan_provider_registry()

    assert outcomes["virustotal"].message == "vt ok"
    assert outcomes["llm_agent"].message == "llm ok"


def test_scan_passed_ignores_skipped_provider_results() -> None:
    version = PluginVersion()
    version.provider_results = [
        ReviewProviderResult(provider="clamav", kind="scan", mode="skipped", passed=False),
        ReviewProviderResult(provider="virustotal", kind="scan", mode="real", passed=True),
    ]

    assert scan_providers_passed(version) is True


def test_scan_passed_blocks_failed_real_provider_result() -> None:
    version = PluginVersion()
    version.provider_results = [
        ReviewProviderResult(provider="clamav", kind="scan", mode="real", passed=True),
        ReviewProviderResult(provider="llm_agent", kind="scan", mode="real", passed=False),
    ]

    assert scan_providers_passed(version) is False


def test_scan_passed_requires_selected_provider_result() -> None:
    version = PluginVersion()
    version.provider_results = [
        ReviewProviderResult(provider="clamav", kind="scan", mode="real", passed=True),
    ]

    assert scan_providers_passed(version, providers=("clamav",)) is True
    assert scan_providers_passed(version, providers=("clamav", "llm_agent")) is False


def test_format_clamav_reply() -> None:
    clean = format_clamav_reply("stream: OK", file_size=2048)
    assert clean.passed is True
    assert "no signature match" in clean.message
    assert "artifact_size=2.0 KiB" in clean.message
    assert 'clamd_reply="stream: OK"' in clean.message

    infected = format_clamav_reply("stream: Eicar-Test-Signature FOUND", file_size=4096)
    assert infected.passed is False
    assert infected.mode == "real"
    assert "Eicar-Test-Signature" in infected.message
    assert "artifact_size=4.0 KiB" in infected.message


@pytest.mark.asyncio
async def test_scan_virustotal_rejects_files_over_direct_upload_limit(tmp_path) -> None:
    artifact = tmp_path / "plugin.zip"
    artifact.write_bytes(b"123456")

    outcome = await scan_virustotal(
        artifact,
        {
            "api_key": "test-key",
            "timeout_seconds": 1,
            "poll_interval_seconds": 1,
            "max_poll_interval_seconds": 2,
            "max_poll_attempts": 1,
            "max_wait_seconds": 30,
            "max_direct_upload_bytes": 5,
        },
    )

    assert outcome.passed is False
    assert outcome.mode == "error"
    assert "exceeds direct upload limit" in outcome.message


@pytest.mark.asyncio
async def test_scan_virustotal_reuses_existing_file_report(tmp_path, monkeypatch) -> None:
    import httpx

    artifact = tmp_path / "plugin.zip"
    artifact.write_bytes(b"clean")
    calls: list[str] = []

    class FakeClient:
        def __init__(self, *, timeout):
            self.timeout = timeout

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def get(self, url, headers):
            calls.append(f"GET {url}")
            return httpx.Response(
                200,
                json={
                    "data": {
                        "attributes": {
                            "last_analysis_stats": {
                                "malicious": 0,
                                "suspicious": 0,
                                "harmless": 1,
                                "undetected": 63,
                            }
                        }
                    }
                },
                request=httpx.Request("GET", url),
            )

        async def post(self, url, headers, files):
            calls.append(f"POST {url}")
            return httpx.Response(200, json={}, request=httpx.Request("POST", url))

    monkeypatch.setattr("astrbot_registry.services.scan_providers.virustotal.httpx.AsyncClient", FakeClient)

    outcome = await scan_virustotal(
        artifact,
        {
            "api_key": "test-key",
            "timeout_seconds": 1,
            "poll_interval_seconds": 1,
            "max_poll_interval_seconds": 2,
            "max_poll_attempts": 1,
            "max_wait_seconds": 30,
            "max_direct_upload_bytes": 1024,
        },
    )

    assert outcome.passed is True
    assert outcome.mode == "real"
    assert "analysis_id=file:" in outcome.message
    assert len([call for call in calls if call.startswith("POST")]) == 0


@pytest.mark.asyncio
async def test_scan_virustotal_uploads_and_returns_pending_analysis(tmp_path, monkeypatch) -> None:
    import httpx

    artifact = tmp_path / "plugin.zip"
    artifact.write_bytes(b"clean")

    class FakeClient:
        def __init__(self, *, timeout):
            self.timeout = timeout

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def get(self, url, headers):
            return httpx.Response(404, json={}, request=httpx.Request("GET", url))

        async def post(self, url, headers, files):
            return httpx.Response(
                200,
                json={"data": {"id": "analysis-1"}},
                request=httpx.Request("POST", url),
            )

    monkeypatch.setattr("astrbot_registry.services.scan_providers.virustotal.httpx.AsyncClient", FakeClient)

    outcome = await scan_virustotal(
        artifact,
        {
            "api_key": "test-key",
            "timeout_seconds": 1,
            "poll_interval_seconds": 10,
            "max_poll_interval_seconds": 120,
            "max_poll_attempts": 24,
            "max_wait_seconds": 1800,
            "max_direct_upload_bytes": 1024,
        },
    )

    assert outcome.passed is None
    assert outcome.mode == "pending"
    assert outcome.virustotal_analysis_id == "analysis-1"
    assert outcome.virustotal_file_sha256 is not None
    assert outcome.virustotal_next_poll_at is not None
    assert "VirusTotal analysis pending" in outcome.message


@pytest.mark.asyncio
async def test_poll_virustotal_analysis_returns_real_result_when_completed(monkeypatch) -> None:
    import httpx

    class FakeClient:
        def __init__(self, *, timeout):
            self.timeout = timeout

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def get(self, url, headers):
            return httpx.Response(
                200,
                json={
                    "data": {
                        "attributes": {
                            "status": "completed",
                            "stats": {
                                "malicious": 0,
                                "suspicious": 0,
                                "harmless": 1,
                                "undetected": 63,
                            },
                        }
                    }
                },
                request=httpx.Request("GET", url),
            )

    monkeypatch.setattr("astrbot_registry.services.scan_providers.virustotal.httpx.AsyncClient", FakeClient)

    outcome = await poll_virustotal_analysis_once(
        "analysis-1",
        {
            "api_key": "test-key",
            "timeout_seconds": 1,
        },
    )

    assert outcome.passed is True
    assert outcome.mode == "real"
    assert outcome.virustotal_analysis_id == "analysis-1"


@pytest.mark.asyncio
async def test_scan_virustotal_falls_back_to_file_report_after_upload_conflict(
    tmp_path,
    monkeypatch,
) -> None:
    import httpx

    artifact = tmp_path / "plugin.zip"
    artifact.write_bytes(b"clean")
    file_report_calls = 0

    class FakeClient:
        def __init__(self, *, timeout):
            self.timeout = timeout

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def get(self, url, headers):
            nonlocal file_report_calls
            if "/files/" in url:
                file_report_calls += 1
                if file_report_calls == 1:
                    return httpx.Response(404, json={}, request=httpx.Request("GET", url))
                return httpx.Response(
                    200,
                    json={
                        "data": {
                            "attributes": {
                                "last_analysis_stats": {
                                    "malicious": 0,
                                    "suspicious": 0,
                                    "harmless": 1,
                                    "undetected": 63,
                                }
                            }
                        }
                    },
                    request=httpx.Request("GET", url),
                )
            return httpx.Response(500, json={}, request=httpx.Request("GET", url))

        async def post(self, url, headers, files):
            return httpx.Response(409, json={}, request=httpx.Request("POST", url))

    monkeypatch.setattr("astrbot_registry.services.scan_providers.virustotal.httpx.AsyncClient", FakeClient)

    outcome = await scan_virustotal(
        artifact,
        {
            "api_key": "test-key",
            "timeout_seconds": 1,
            "poll_interval_seconds": 1,
            "max_poll_interval_seconds": 2,
            "max_poll_attempts": 1,
            "max_wait_seconds": 30,
            "max_direct_upload_bytes": 1024,
        },
    )

    assert outcome.passed is True
    assert file_report_calls == 2


def test_build_llm_context_truncates_and_notes_limit(tmp_path) -> None:
    import zipfile

    artifact = tmp_path / "plugin.zip"
    with zipfile.ZipFile(artifact, "w") as zf:
        zf.writestr("metadata.yaml", "name: test\n")
        zf.writestr("main.py", "print('hello')\n" * 200)

    context, truncated = build_llm_context(artifact, 1200)

    assert truncated is True
    assert "Context truncated" in context
    assert "File: metadata.yaml" in context


def test_parse_llm_response_requires_json_object() -> None:
    result = parse_llm_response('{"pass":true,"risk_level":"low","summary":"ok","findings":[]}')

    assert result["pass"] is True
    assert result["risk_level"] == "low"


def test_parse_llm_response_extracts_json_from_markdown_fence() -> None:
    result = parse_llm_response(
        '```json\n{"pass":true,"risk_level":"low","summary":"ok","findings":[]}\n```'
    )

    assert result["pass"] is True
    assert result["risk_level"] == "low"


def test_parse_llm_response_extracts_json_from_extra_text() -> None:
    result = parse_llm_response(
        'Here is the result: {"pass":false,"risk_level":"high","summary":"bad","findings":[{"reason":"x"}]} done.'
    )

    assert result["pass"] is False
    assert result["risk_level"] == "high"


@pytest.mark.asyncio
async def test_scan_llm_uses_structured_response(tmp_path, monkeypatch) -> None:
    import json
    import zipfile

    artifact = tmp_path / "plugin.zip"
    with zipfile.ZipFile(artifact, "w") as zf:
        zf.writestr("metadata.yaml", "name: test\n")
        zf.writestr("main.py", "print('hello')\n")

    async def fake_call_llm_agent(context, truncated, config):
        return json.dumps(
            {
                "pass": True,
                "risk_level": "low",
                "summary": "No obvious issue",
                "findings": [],
            }
        )

    monkeypatch.setattr("astrbot_registry.services.scan_providers.llm_agent.call_llm_agent", fake_call_llm_agent)

    outcome = await scan_llm(
        artifact,
        {
            "base_url": "https://api.example.com/v1",
            "model": "gpt-test",
            "api_key": "secret",
            "max_context_chars": 24000,
        },
    )

    assert outcome.passed is True
    assert outcome.mode == "real"
    assert '"risk_level":"low"' in outcome.message


@pytest.mark.asyncio
async def test_scan_llm_fails_high_risk_even_when_model_passes(tmp_path, monkeypatch) -> None:
    import json
    import zipfile

    artifact = tmp_path / "plugin.zip"
    with zipfile.ZipFile(artifact, "w") as zf:
        zf.writestr("main.py", "eval(input())\n")

    async def fake_call_llm_agent(context, truncated, config):
        return json.dumps(
            {
                "pass": True,
                "risk_level": "high",
                "summary": "Remote code execution risk",
                "findings": [],
            }
        )

    monkeypatch.setattr("astrbot_registry.services.scan_providers.llm_agent.call_llm_agent", fake_call_llm_agent)

    outcome = await scan_llm(
        artifact,
        {
            "base_url": "https://api.example.com/v1",
            "model": "gpt-test",
            "api_key": "secret",
            "max_context_chars": 24000,
        },
    )

    assert outcome.passed is False
    assert '"risk_level":"high"' in outcome.message


@pytest.mark.asyncio
async def test_scan_llm_downgrades_uncertainty_only_high_risk(tmp_path, monkeypatch) -> None:
    import json
    import zipfile

    artifact = tmp_path / "plugin.zip"
    with zipfile.ZipFile(artifact, "w") as zf:
        zf.writestr("main.py", "print('hello')\n")

    async def fake_call_llm_agent(context, truncated, config):
        return json.dumps(
            {
                "pass": False,
                "risk_level": "high",
                "summary": "Plugin source code is incomplete. Hidden malicious behavior cannot be ruled out.",
                "findings": [
                    {
                        "severity": "high",
                        "category": "Incomplete Code",
                        "file": "main.py",
                        "reason": "The full logic is not visible for review.",
                        "recommendation": "Request the full source code for complete review.",
                    }
                ],
            }
        )

    monkeypatch.setattr("astrbot_registry.services.scan_providers.llm_agent.call_llm_agent", fake_call_llm_agent)

    outcome = await scan_llm(
        artifact,
        {
            "base_url": "https://api.example.com/v1",
            "model": "gpt-test",
            "api_key": "secret",
            "max_context_chars": 24000,
        },
    )

    assert outcome.passed is True
    assert '"risk_level":"medium"' in outcome.message
    assert "normalization_note" in outcome.message
