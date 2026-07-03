from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient
from astrbot_registry.api.public import public_router


def test_health(client: TestClient) -> None:
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_plugins_mocked(client: TestClient) -> None:
    with patch(
        "astrbot_registry.api.public.generate_registry_json",
        new_callable=AsyncMock,
        return_value={"astrbot-plugin-test": {"desc": "Test plugin"}},
    ):
        response = client.get("/api/v1/plugins")
        assert response.status_code == 200
        assert "astrbot-plugin-test" in response.json()


def test_plugins_md5_mocked(client: TestClient) -> None:
    with patch(
        "astrbot_registry.api.public.get_registry_md5",
        new_callable=AsyncMock,
        return_value="abc123",
    ):
        response = client.get("/api/v1/plugins-md5")
        assert response.status_code == 200
        assert response.json() == {"md5": "abc123"}


def test_plugins_md5_json_alias(client: TestClient) -> None:
    with patch(
        "astrbot_registry.api.public.get_registry_md5",
        new_callable=AsyncMock,
        return_value="abc123",
    ):
        response = client.get("/api/v1/plugins-md5.json")
        assert response.status_code == 200
        assert response.json() == {"md5": "abc123"}


def test_plugins_search_path_alias(client: TestClient) -> None:
    paths = {route.path for route in public_router.routes if hasattr(route, "path")}
    assert "/plugins/search" in paths


def test_plugins_stats_path_alias(client: TestClient) -> None:
    paths = {route.path for route in public_router.routes if hasattr(route, "path")}
    assert "/plugins/stats" in paths
