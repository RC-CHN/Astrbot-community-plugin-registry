from astrbot_registry.api.admin import admin_router


def test_pending_plugins_route_precedes_plugin_detail_route() -> None:
    paths = [route.path for route in admin_router.routes if hasattr(route, "path")]

    assert paths.index("/admin/plugins/pending") < paths.index("/admin/plugins/{plugin_id}")
