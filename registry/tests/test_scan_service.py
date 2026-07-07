import pytest

from astrbot_registry.services.scan_service import (
    ScanOutcome,
    _build_llm_context,
    _can_mark_build_scanning,
    _format_virustotal_result,
    _poll_virustotal_analysis,
    _parse_llm_response,
    _scan_llm,
    _scan_selected_providers,
    _scan_virustotal,
)
from astrbot_registry.models import PluginVersion


def test_format_virustotal_result_passes_clean_analysis() -> None:
    outcome = _format_virustotal_result(
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
    outcome = _format_virustotal_result(
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
async def test_selected_scan_providers_run_concurrently(monkeypatch) -> None:
    import asyncio

    version = PluginVersion(
        s3_key="plugins/example.zip",
        download_url="https://example.test/plugin.zip",
    )
    vt_started = asyncio.Event()
    llm_started = asyncio.Event()

    async def fake_virustotal_for_version(*args, **kwargs):
        vt_started.set()
        await llm_started.wait()
        return ScanOutcome(True, "vt ok", "real")

    async def fake_llm_for_version(*args, **kwargs):
        llm_started.set()
        await vt_started.wait()
        return ScanOutcome(True, "llm ok", "real")

    monkeypatch.setattr(
        "astrbot_registry.services.scan_service._scan_virustotal_for_version",
        fake_virustotal_for_version,
    )
    monkeypatch.setattr(
        "astrbot_registry.services.scan_service._scan_llm_for_version",
        fake_llm_for_version,
    )

    outcomes = await asyncio.wait_for(
        _scan_selected_providers(
            version,
            {"virustotal", "llm_agent"},
            {"pass_when_unconfigured": True, "message": "skipped"},
            vt_config={"api_key": "vt-key"},
            llm_config={
                "enabled": True,
                "base_url": "https://api.example.test/v1",
                "model": "test-model",
                "api_key": "llm-key",
            },
            local_path=None,
        ),
        timeout=1,
    )

    assert outcomes["virustotal"].message == "vt ok"
    assert outcomes["llm_agent"].message == "llm ok"


@pytest.mark.asyncio
async def test_scan_virustotal_rejects_files_over_direct_upload_limit(tmp_path) -> None:
    artifact = tmp_path / "plugin.zip"
    artifact.write_bytes(b"123456")

    outcome = await _scan_virustotal(
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

    monkeypatch.setattr("astrbot_registry.services.scan_service.httpx.AsyncClient", FakeClient)

    outcome = await _scan_virustotal(
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

    monkeypatch.setattr("astrbot_registry.services.scan_service.httpx.AsyncClient", FakeClient)

    outcome = await _scan_virustotal(
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

    monkeypatch.setattr("astrbot_registry.services.scan_service.httpx.AsyncClient", FakeClient)

    outcome = await _poll_virustotal_analysis(
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

    monkeypatch.setattr("astrbot_registry.services.scan_service.httpx.AsyncClient", FakeClient)

    outcome = await _scan_virustotal(
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

    context, truncated = _build_llm_context(artifact, 1200)

    assert truncated is True
    assert "Context truncated" in context
    assert "File: metadata.yaml" in context


def test_parse_llm_response_requires_json_object() -> None:
    result = _parse_llm_response('{"pass":true,"risk_level":"low","summary":"ok","findings":[]}')

    assert result["pass"] is True
    assert result["risk_level"] == "low"


def test_parse_llm_response_extracts_json_from_markdown_fence() -> None:
    result = _parse_llm_response(
        '```json\n{"pass":true,"risk_level":"low","summary":"ok","findings":[]}\n```'
    )

    assert result["pass"] is True
    assert result["risk_level"] == "low"


def test_parse_llm_response_extracts_json_from_extra_text() -> None:
    result = _parse_llm_response(
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

    monkeypatch.setattr("astrbot_registry.services.scan_service._call_llm_agent", fake_call_llm_agent)

    outcome = await _scan_llm(
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

    monkeypatch.setattr("astrbot_registry.services.scan_service._call_llm_agent", fake_call_llm_agent)

    outcome = await _scan_llm(
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
