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


def test_user_registration_migration_adds_user_state_and_invites() -> None:
    migration = Path(__file__).resolve().parents[1] / "alembic/versions/0006_user_registration.py"
    content = migration.read_text(encoding="utf-8")

    assert "user_invites" in content
    assert "ck_users_status" in content
    assert "role IN ('admin', 'reviewer', 'user')" in content
    assert "uq_users_email" in content


def test_submission_request_migration_adds_request_table() -> None:
    migration = Path(__file__).resolve().parents[1] / "alembic/versions/0007_submission_requests.py"
    content = migration.read_text(encoding="utf-8")

    assert "plugin_submission_requests" in content
    assert "user_message" in content
    assert "admin_message" in content
    assert "need_info" not in content
    assert "idx_submission_requests_status_created" in content
