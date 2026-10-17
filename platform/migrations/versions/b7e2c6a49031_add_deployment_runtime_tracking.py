"""add deployment runtime tracking

Revision ID: b7e2c6a49031
Revises: 9f70f9a04744
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "b7e2c6a49031"
down_revision: Union[str, Sequence[str], None] = "9f70f9a04744"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "deployments",
        sa.Column(
            "runtime_status",
            sa.String(length=30),
            nullable=False,
            server_default="unverified",
        ),
    )

    op.add_column(
        "deployments",
        sa.Column(
            "runtime_reason",
            sa.String(length=255),
            nullable=True,
        ),
    )

    op.add_column(
        "deployments",
        sa.Column(
            "runtime_checked_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column("deployments", "runtime_checked_at")
    op.drop_column("deployments", "runtime_reason")
    op.drop_column("deployments", "runtime_status")
