from astrbot_registry.models import Plugin, PluginVersion, SecurityScan, User


def test_status_and_role_constraints_are_declared() -> None:
    constraint_names = {
        constraint.name
        for table in [Plugin.__table__, PluginVersion.__table__, User.__table__]
        for constraint in table.constraints
    }

    assert "ck_plugins_status" in constraint_names
    assert "ck_versions_build_status" in constraint_names
    assert "ck_versions_version_status" in constraint_names
    assert "ck_users_role" in constraint_names


def test_latest_partial_unique_index_is_declared() -> None:
    index = next(
        item
        for item in PluginVersion.__table__.indexes
        if item.name == "idx_versions_is_latest_per_plugin"
    )

    assert index.unique is True
    assert str(index.dialect_options["postgresql"]["where"]) == "is_latest = true"


def test_security_scan_version_is_unique() -> None:
    unique_constraints = [
        constraint
        for constraint in SecurityScan.__table__.constraints
        if getattr(constraint, "columns", None) is not None and constraint.name is None
    ]
    assert any({"version_id"} == set(constraint.columns.keys()) for constraint in unique_constraints)
