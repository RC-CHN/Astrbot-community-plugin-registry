from pathlib import Path


def test_initial_migration_contains_core_tables() -> None:
    migration = Path("alembic/versions/0001_initial_registry_schema.py")
    content = migration.read_text(encoding="utf-8")

    for table_name in [
        "users",
        "plugins",
        "plugin_versions",
        "security_scans",
        "plugin_version_stats",
        "webhook_events",
        "system_config",
    ]:
        assert f'"{table_name}"' in content

    assert "idx_versions_is_latest_per_plugin" in content
    assert "uq_version_stats_version_date" in content
    assert "CREATE EXTENSION IF NOT EXISTS pgcrypto" in content
    assert "gen_random_uuid()" in content
