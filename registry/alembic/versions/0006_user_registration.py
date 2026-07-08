"""user registration

Revision ID: 0006_user_registration
Revises: 0005_dup_metadata_versions
Create Date: 2026-07-08
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0006_user_registration"
down_revision: Union[str, None] = "0005_dup_metadata_versions"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("users", sa.Column("email", sa.String(length=255), nullable=True))
    op.add_column(
        "users",
        sa.Column("status", sa.String(length=50), server_default=sa.text("'active'"), nullable=False),
    )
    op.create_unique_constraint("uq_users_email", "users", ["email"])
    op.drop_constraint("ck_users_role", "users", type_="check")
    op.create_check_constraint("ck_users_role", "users", "role IN ('admin', 'reviewer', 'user')")
    op.create_check_constraint(
        "ck_users_status",
        "users",
        "status IN ('pending_approval', 'active', 'disabled')",
    )

    op.create_table(
        "user_invites",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("code_hash", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=50), server_default=sa.text("'active'"), nullable=False),
        sa.Column("max_uses", sa.Integer(), server_default=sa.text("1"), nullable=False),
        sa.Column("used_count", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("expires_at", postgresql.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", postgresql.TIMESTAMP(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", postgresql.TIMESTAMP(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("status IN ('active', 'disabled')", name="ck_user_invites_status"),
        sa.CheckConstraint("max_uses > 0", name="ck_user_invites_max_uses_positive"),
        sa.CheckConstraint("used_count >= 0", name="ck_user_invites_used_count_nonnegative"),
        sa.CheckConstraint("used_count <= max_uses", name="ck_user_invites_used_count_lte_max"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code_hash"),
    )


def downgrade() -> None:
    op.drop_table("user_invites")
    op.drop_constraint("ck_users_status", "users", type_="check")
    op.drop_constraint("ck_users_role", "users", type_="check")
    op.create_check_constraint("ck_users_role", "users", "role IN ('admin', 'reviewer')")
    op.drop_constraint("uq_users_email", "users", type_="unique")
    op.drop_column("users", "status")
    op.drop_column("users", "email")
