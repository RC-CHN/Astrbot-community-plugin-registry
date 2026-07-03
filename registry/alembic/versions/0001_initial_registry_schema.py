"""initial registry schema

Revision ID: 0001_initial
Revises:
Create Date: 2026-07-03
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001_initial"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto")
    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("username", sa.String(length=100), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("role", sa.String(length=50), server_default=sa.text("'reviewer'"), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("created_at", postgresql.TIMESTAMP(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", postgresql.TIMESTAMP(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("role IN ('admin', 'reviewer')", name="ck_users_role"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("username"),
    )

    op.create_table(
        "plugins",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("plugin_key", sa.String(length=255), nullable=False),
        sa.Column("display_name", sa.String(length=255), nullable=True),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("author", sa.String(length=255), nullable=False),
        sa.Column("repo_url", sa.String(length=512), nullable=True),
        sa.Column("social_link", sa.String(length=512), nullable=True),
        sa.Column("category", sa.String(length=100), nullable=True),
        sa.Column("logo_s3_key", sa.String(length=512), nullable=True),
        sa.Column("stars", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("pinned", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("support_platforms", postgresql.ARRAY(sa.String()), nullable=True),
        sa.Column("astrbot_version", sa.String(length=100), nullable=True),
        sa.Column("status", sa.String(length=50), server_default=sa.text("'pending'"), nullable=False),
        sa.Column("review_status", sa.String(length=50), server_default=sa.text("'pending'"), nullable=False),
        sa.Column("created_at", postgresql.TIMESTAMP(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", postgresql.TIMESTAMP(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("stars >= 0", name="ck_plugins_stars_nonnegative"),
        sa.CheckConstraint("status IN ('pending', 'active', 'disabled', 'deleted')", name="ck_plugins_status"),
        sa.CheckConstraint("review_status IN ('pending', 'approved', 'skipped', 'rejected')", name="ck_plugins_review_status"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("plugin_key"),
    )
    op.create_index("idx_plugins_author", "plugins", ["author"])
    op.create_index("idx_plugins_category", "plugins", ["category"])
    op.create_index("idx_plugins_status", "plugins", ["status"])

    op.create_table(
        "tags",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name"),
    )

    op.create_table(
        "system_config",
        sa.Column("key", sa.String(length=255), nullable=False),
        sa.Column("value", sa.Text(), nullable=False),
        sa.Column("updated_at", postgresql.TIMESTAMP(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("key"),
    )

    op.create_table(
        "plugin_versions",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("plugin_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("version", sa.String(length=50), nullable=False),
        sa.Column("commit_sha", sa.String(length=64), nullable=True),
        sa.Column("source_type", sa.String(length=32), server_default=sa.text("'git_auto'"), nullable=False),
        sa.Column("download_url", sa.String(length=512), nullable=True),
        sa.Column("s3_key", sa.String(length=512), nullable=True),
        sa.Column("file_size", sa.BigInteger(), nullable=True),
        sa.Column("metadata_raw", sa.Text(), nullable=True),
        sa.Column("changelog", sa.Text(), nullable=True),
        sa.Column("build_status", sa.String(length=50), server_default=sa.text("'pending'"), nullable=False),
        sa.Column("build_log", sa.Text(), nullable=True),
        sa.Column("version_status", sa.String(length=50), server_default=sa.text("'draft'"), nullable=False),
        sa.Column("is_latest", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", postgresql.TIMESTAMP(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", postgresql.TIMESTAMP(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("NOT is_latest OR (version_status = 'active' AND build_status = 'success')", name="ck_versions_latest_active_success"),
        sa.CheckConstraint("build_status <> 'success' OR (s3_key IS NOT NULL AND download_url IS NOT NULL)", name="ck_versions_success_has_artifact"),
        sa.CheckConstraint("build_status IN ('pending', 'building', 'success', 'failed', 'scanning')", name="ck_versions_build_status"),
        sa.CheckConstraint("file_size IS NULL OR file_size >= 0", name="ck_versions_file_size"),
        sa.CheckConstraint("source_type IN ('git_auto', 'manual_upload')", name="ck_versions_source_type"),
        sa.CheckConstraint("version_status IN ('draft', 'active', 'deprecated', 'deleted')", name="ck_versions_version_status"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["plugin_id"], ["plugins.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("plugin_id", "version"),
    )
    op.create_index("idx_versions_build_status", "plugin_versions", ["build_status"])
    op.create_index("idx_versions_plugin", "plugin_versions", ["plugin_id"])
    op.create_index("idx_versions_status", "plugin_versions", ["version_status"])
    op.create_index(
        "idx_versions_is_latest_per_plugin",
        "plugin_versions",
        ["plugin_id"],
        unique=True,
        postgresql_where=sa.text("is_latest = true"),
    )

    op.create_table(
        "plugin_tags",
        sa.Column("plugin_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tag_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.ForeignKeyConstraint(["plugin_id"], ["plugins.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["tag_id"], ["tags.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("plugin_id", "tag_id"),
    )

    op.create_table(
        "plugin_i18n",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("plugin_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("locale", sa.String(length=10), nullable=False),
        sa.Column("data", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.ForeignKeyConstraint(["plugin_id"], ["plugins.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("plugin_id", "locale"),
    )

    op.create_table(
        "security_scans",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("version_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("virustotal_pass", sa.Boolean(), nullable=True),
        sa.Column("virustotal_msg", sa.Text(), nullable=True),
        sa.Column("virustotal_mode", sa.String(length=32), server_default=sa.text("'pending'"), nullable=False),
        sa.Column("llm_agent_pass", sa.Boolean(), nullable=True),
        sa.Column("llm_agent_msg", sa.Text(), nullable=True),
        sa.Column("llm_agent_mode", sa.String(length=32), server_default=sa.text("'pending'"), nullable=False),
        sa.Column("scanned_at", postgresql.TIMESTAMP(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("llm_agent_mode IN ('pending', 'real', 'skipped', 'error')", name="ck_security_scans_llm_agent_mode"),
        sa.CheckConstraint("virustotal_mode IN ('pending', 'real', 'skipped', 'error')", name="ck_security_scans_virustotal_mode"),
        sa.ForeignKeyConstraint(["version_id"], ["plugin_versions.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("version_id"),
    )

    op.create_table(
        "plugin_version_stats",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("version_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("date", sa.Date(), server_default=sa.text("CURRENT_DATE"), nullable=False),
        sa.Column("download_count", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("install_count", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.CheckConstraint("download_count >= 0", name="ck_version_stats_download_count"),
        sa.CheckConstraint("install_count >= 0", name="ck_version_stats_install_count"),
        sa.ForeignKeyConstraint(["version_id"], ["plugin_versions.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("version_id", "date", name="uq_version_stats_version_date"),
    )
    op.create_index("idx_version_stats_date", "plugin_version_stats", ["date"])
    op.create_index("idx_version_stats_version", "plugin_version_stats", ["version_id"])

    op.create_table(
        "webhook_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("plugin_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("event_type", sa.String(length=50), nullable=False),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("triggered_version_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("status", sa.String(length=50), server_default=sa.text("'pending'"), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", postgresql.TIMESTAMP(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("event_type IN ('push', 'release', 'tag', 'manual')", name="ck_webhook_events_event_type"),
        sa.CheckConstraint("status IN ('pending', 'success', 'failed', 'ignored')", name="ck_webhook_events_status"),
        sa.ForeignKeyConstraint(["plugin_id"], ["plugins.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["triggered_version_id"], ["plugin_versions.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("webhook_events")
    op.drop_index("idx_version_stats_version", table_name="plugin_version_stats")
    op.drop_index("idx_version_stats_date", table_name="plugin_version_stats")
    op.drop_table("plugin_version_stats")
    op.drop_table("security_scans")
    op.drop_table("plugin_i18n")
    op.drop_table("plugin_tags")
    op.drop_index("idx_versions_is_latest_per_plugin", table_name="plugin_versions")
    op.drop_index("idx_versions_status", table_name="plugin_versions")
    op.drop_index("idx_versions_plugin", table_name="plugin_versions")
    op.drop_index("idx_versions_build_status", table_name="plugin_versions")
    op.drop_table("plugin_versions")
    op.drop_table("system_config")
    op.drop_table("tags")
    op.drop_index("idx_plugins_status", table_name="plugins")
    op.drop_index("idx_plugins_category", table_name="plugins")
    op.drop_index("idx_plugins_author", table_name="plugins")
    op.drop_table("plugins")
    op.drop_table("users")
