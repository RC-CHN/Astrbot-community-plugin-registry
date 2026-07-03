from astrbot_registry.services.config_service import build_config_response


def test_config_response_includes_effective_values() -> None:
    response = build_config_response({"PUBLIC_CACHE_MAX_AGE": "123"})

    assert response["values"]["PUBLIC_CACHE_MAX_AGE"] == "123"
    assert response["effective_values"]["PUBLIC_CACHE_MAX_AGE"] == "123"


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
