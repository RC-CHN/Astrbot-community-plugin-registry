"""allow duplicate metadata versions

Revision ID: 0005_dup_metadata_versions
Revises: 0004_worker_task_observability
Create Date: 2026-07-08
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0005_dup_metadata_versions"
down_revision: Union[str, None] = "0004_worker_task_observability"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("plugin_versions", sa.Column("source_ref", sa.String(length=255), nullable=True))
    op.drop_constraint("plugin_versions_plugin_id_version_key", "plugin_versions", type_="unique")
    op.create_index("idx_versions_plugin_version", "plugin_versions", ["plugin_id", "version"], unique=False)
    op.create_index(
        "idx_versions_git_commit_per_plugin",
        "plugin_versions",
        ["plugin_id", "commit_sha"],
        unique=True,
        postgresql_where=sa.text("source_type = 'git_auto' AND commit_sha ~ '^[0-9a-fA-F]{40,64}$'"),
    )


def downgrade() -> None:
    op.drop_index("idx_versions_git_commit_per_plugin", table_name="plugin_versions")
    op.drop_index("idx_versions_plugin_version", table_name="plugin_versions")
    op.create_unique_constraint(
        "plugin_versions_plugin_id_version_key",
        "plugin_versions",
        ["plugin_id", "version"],
    )
    op.drop_column("plugin_versions", "source_ref")
