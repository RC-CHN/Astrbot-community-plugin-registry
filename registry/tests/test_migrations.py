from pathlib import Path


def test_initial_migration_contains_core_tables() -> None:
    migration = Path(__file__).resolve().parents[1] / "alembic/versions/0001_initial_registry_schema.py"
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


def test_duplicate_metadata_version_migration_changes_version_identity() -> None:
    migration = (
        Path(__file__).resolve().parents[1]
        / "alembic/versions/0005_dup_metadata_versions.py"
    )
    content = migration.read_text(encoding="utf-8")

    assert "source_ref" in content
    assert "plugin_versions_plugin_id_version_key" in content
    assert "idx_versions_plugin_version" in content
    assert "idx_versions_git_commit_per_plugin" in content
    assert "source_type = 'git_auto' AND commit_sha ~ '^[0-9a-fA-F]{40,64}$'" in content
