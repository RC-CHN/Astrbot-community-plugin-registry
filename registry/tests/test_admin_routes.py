import pytest

from astrbot_registry.api.admin import admin_router
from astrbot_registry.api.admin import update_config_endpoint
from astrbot_registry.schemas.admin import ConfigUpdate


def test_pending_plugins_route_precedes_plugin_detail_route() -> None:
    paths = [route.path for route in admin_router.routes if hasattr(route, "path")]

    assert paths.index("/admin/plugins/pending") < paths.index("/admin/plugins/{plugin_id}")


@pytest.mark.asyncio
async def test_update_config_endpoint_returns_config_response(monkeypatch) -> None:
    async def fake_update_config(db, values):
        assert values == {"S3_PUBLIC_URL": "http://example.test/s3"}
        return {
            "values": {"S3_PUBLIC_URL": "http://example.test/s3"},
            "effective_values": {"S3_PUBLIC_URL": "http://example.test/s3"},
            "sensitive_status": {},
            "sensitive_keys": [],
            "deployment_values": {},
        }

    monkeypatch.setattr("astrbot_registry.api.admin.update_config", fake_update_config)

    result = await update_config_endpoint(
        ConfigUpdate(values={"S3_PUBLIC_URL": "http://example.test/s3"}),
        db=object(),  # type: ignore[arg-type]
        current_user=object(),  # type: ignore[arg-type]
    )

    assert result["values"] == {"S3_PUBLIC_URL": "http://example.test/s3"}
    assert result["effective_values"] == {"S3_PUBLIC_URL": "http://example.test/s3"}
