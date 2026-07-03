"""add plugin review status

Revision ID: 0002_review_status
Revises: 0001_initial
Create Date: 2026-07-03
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0002_review_status"
down_revision: Union[str, None] = "0001_initial"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "plugins",
        sa.Column(
            "review_status",
            sa.String(length=50),
            server_default=sa.text("'pending'"),
            nullable=False,
        ),
    )
    op.execute(
        "UPDATE plugins SET review_status = CASE "
        "WHEN status = 'active' THEN 'approved' "
        "WHEN status = 'disabled' THEN 'rejected' "
        "ELSE 'pending' END"
    )
    op.create_check_constraint(
        "ck_plugins_review_status",
        "plugins",
        "review_status IN ('pending', 'approved', 'skipped', 'rejected')",
    )


def downgrade() -> None:
    op.drop_constraint("ck_plugins_review_status", "plugins", type_="check")
    op.drop_column("plugins", "review_status")
