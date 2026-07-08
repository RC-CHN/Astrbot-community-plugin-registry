from sqlalchemy import UniqueConstraint

from astrbot_registry.models import (
    Plugin,
    PluginVersion,
    PluginVersionStat,
    ReviewProviderResult,
    SecurityScan,
    SystemConfig,
    WorkerTask,
    User,
    WebhookEvent,
)


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
    assert "ck_worker_tasks_status" in {constraint.name for constraint in WorkerTask.__table__.constraints}
    assert SystemConfig.__tablename__ == "system_config"
    assert WebhookEvent.__tablename__ == "webhook_events"


def test_worker_task_indexes_are_declared() -> None:
    index_names = {index.name for index in WorkerTask.__table__.indexes}

    assert "idx_worker_tasks_status_created" in index_names
    assert "idx_worker_tasks_plugin_created" in index_names
    assert "idx_worker_tasks_version_created" in index_names
    assert "idx_worker_tasks_type_created" in index_names


def test_latest_partial_unique_index_is_declared() -> None:
    index = next(
        item
        for item in PluginVersion.__table__.indexes
        if item.name == "idx_versions_is_latest_per_plugin"
    )

    assert index.unique is True
    assert str(index.dialect_options["postgresql"]["where"]) == "is_latest = true"


def test_version_identity_allows_duplicate_metadata_versions() -> None:
    unique_constraints = [
        constraint
        for constraint in PluginVersion.__table__.constraints
        if isinstance(constraint, UniqueConstraint)
    ]
    index_names = {index.name for index in PluginVersion.__table__.indexes}
    commit_index = next(
        item
        for item in PluginVersion.__table__.indexes
        if item.name == "idx_versions_git_commit_per_plugin"
    )

    assert not any({"plugin_id", "version"} == set(constraint.columns.keys()) for constraint in unique_constraints)
    assert "source_ref" in PluginVersion.__table__.c
    assert "idx_versions_plugin_version" in index_names
    assert commit_index.unique is True
    assert (
        str(commit_index.dialect_options["postgresql"]["where"])
        == "source_type = 'git_auto' AND commit_sha ~ '^[0-9a-fA-F]{40,64}$'"
    )


def test_security_scan_version_is_unique() -> None:
    unique_constraints = [
        constraint
        for constraint in SecurityScan.__table__.constraints
        if getattr(constraint, "columns", None) is not None and constraint.name is None
    ]
    assert any({"version_id"} == set(constraint.columns.keys()) for constraint in unique_constraints)


def test_security_scan_mode_constraints_are_declared() -> None:
    constraint_names = {constraint.name for constraint in SecurityScan.__table__.constraints}

    assert "ck_security_scans_virustotal_mode" in constraint_names
    assert "ck_security_scans_llm_agent_mode" in constraint_names


def test_review_provider_result_constraints_and_indexes_are_declared() -> None:
    constraint_names = {constraint.name for constraint in ReviewProviderResult.__table__.constraints}
    index_names = {index.name for index in ReviewProviderResult.__table__.indexes}

    assert "uq_review_provider_version_provider" in constraint_names
    assert "ck_review_provider_kind" in constraint_names
    assert "ck_review_provider_mode" in constraint_names
    assert "idx_review_provider_version" in index_names
    assert "idx_review_provider_provider_mode" in index_names


def test_version_stats_constraints_and_indexes_are_declared() -> None:
    constraint_names = {constraint.name for constraint in PluginVersionStat.__table__.constraints}
    index_names = {index.name for index in PluginVersionStat.__table__.indexes}

    assert "uq_version_stats_version_date" in constraint_names
    assert "ck_version_stats_download_count" in constraint_names
    assert "idx_version_stats_version" in index_names
    assert "idx_version_stats_date" in index_names


def test_plugin_updated_at_is_the_only_update_timestamp() -> None:
    assert Plugin.__table__.c.created_at.onupdate is None
    assert Plugin.__table__.c.updated_at.onupdate is not None
