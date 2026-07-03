import pytest

from astrbot_registry.services.scan_service import (
    _format_virustotal_result,
    _scan_virustotal,
)


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
            "max_poll_attempts": 1,
            "max_direct_upload_bytes": 5,
        },
    )

    assert outcome.passed is False
    assert outcome.mode == "error"
    assert "exceeds direct upload limit" in outcome.message
