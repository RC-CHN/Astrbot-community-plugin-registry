from astrbot_registry.services.config_service import EFFECTIVE_CONFIG_DEFAULTS, build_config_response


def test_config_response_includes_effective_values() -> None:
    response = build_config_response({"PUBLIC_CACHE_MAX_AGE": "123"})

    assert response["values"]["PUBLIC_CACHE_MAX_AGE"] == "123"
    assert response["effective_values"]["PUBLIC_CACHE_MAX_AGE"] == "123"


def test_config_response_includes_virustotal_runtime_defaults() -> None:
    response = build_config_response({})

    for key in [
        "VIRUSTOTAL_TIMEOUT_SECONDS",
        "VIRUSTOTAL_POLL_INTERVAL_SECONDS",
        "VIRUSTOTAL_MAX_POLL_INTERVAL_SECONDS",
        "VIRUSTOTAL_MAX_POLL_ATTEMPTS",
        "VIRUSTOTAL_MAX_WAIT_SECONDS",
        "VIRUSTOTAL_MAX_DIRECT_UPLOAD_BYTES",
    ]:
        assert response["effective_values"][key] == str(EFFECTIVE_CONFIG_DEFAULTS[key])


def test_config_response_includes_llm_runtime_defaults() -> None:
    response = build_config_response({})

    assert response["effective_values"]["LLM_AGENT_ENABLED"] == "False"
    assert response["effective_values"]["LLM_AGENT_BASE_URL"] == ""
    assert response["effective_values"]["LLM_AGENT_MODEL"] == ""
    assert response["effective_values"]["LLM_AGENT_MAX_CONTEXT_CHARS"] == "200000"
    assert "LLM_AGENT_API_KEY" not in response["effective_values"]
    assert "LLM_AGENT_API_KEY" in response["sensitive_keys"]


def test_config_response_redacts_sensitive_values() -> None:
    response = build_config_response({"GITHUB_WEBHOOK_SECRET": "secret"})

    assert "GITHUB_WEBHOOK_SECRET" not in response["values"]
    assert "GITHUB_WEBHOOK_SECRET" not in response["effective_values"]
    assert response["sensitive_status"]["GITHUB_WEBHOOK_SECRET"] is True


def test_config_response_includes_masked_deployment_values() -> None:
    response = build_config_response({})

    assert "DATABASE_URL" in response["deployment_values"]
    assert "JWT_SECRET" in response["deployment_values"]
    assert "change-me-in-production" not in response["deployment_values"]["JWT_SECRET"]
