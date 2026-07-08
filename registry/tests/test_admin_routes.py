import pytest

from astrbot_registry.api.admin import admin_router
from astrbot_registry.api.admin import publish_version
from astrbot_registry.api.admin import update_config_endpoint
from astrbot_registry.schemas.admin import ConfigUpdate, PublishVersionRequest


def test_pending_plugins_route_precedes_plugin_detail_route() -> None:
    paths = [route.path for route in admin_router.routes if hasattr(route, "path")]

    assert paths.index("/admin/plugins/pending") < paths.index("/admin/plugins/{plugin_id}")


def test_inspect_repo_route_precedes_plugin_detail_route() -> None:
    paths = [route.path for route in admin_router.routes if hasattr(route, "path")]

    assert paths.index("/admin/plugins/inspect-repo") < paths.index("/admin/plugins/{plugin_id}")


def test_resolve_ref_route_precedes_plugin_detail_route() -> None:
    paths = [route.path for route in admin_router.routes if hasattr(route, "path")]

    assert paths.index("/admin/plugins/resolve-ref") < paths.index("/admin/plugins/{plugin_id}")


def test_publish_version_route_precedes_version_status_route() -> None:
    paths = [route.path for route in admin_router.routes if hasattr(route, "path")]

    assert paths.index("/admin/plugins/{plugin_id}/versions/{version_id}/publish") < paths.index(
        "/admin/plugins/{plugin_id}/versions/{version_id}/status"
    )


def test_tasks_route_precedes_task_detail_route() -> None:
    paths = [route.path for route in admin_router.routes if hasattr(route, "path")]

    assert paths.index("/admin/tasks") < paths.index("/admin/tasks/{task_id}")


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


@pytest.mark.asyncio
async def test_publish_version_endpoint_uses_atomic_service(monkeypatch) -> None:
    calls = []

    async def fake_publish_plugin_version(db, plugin_id, version_id, *, review_status):
        calls.append((db, str(plugin_id), str(version_id), review_status))

    monkeypatch.setattr("astrbot_registry.api.admin.publish_plugin_version", fake_publish_plugin_version)

    result = await publish_version(
        "00000000-0000-0000-0000-000000000001",
        "00000000-0000-0000-0000-000000000002",
        PublishVersionRequest(review_status="skipped"),
        db=object(),  # type: ignore[arg-type]
        current_user=object(),  # type: ignore[arg-type]
    )

    assert result == {"status": "published"}
    assert calls[0][1:] == (
        "00000000-0000-0000-0000-000000000001",
        "00000000-0000-0000-0000-000000000002",
        "skipped",
    )
