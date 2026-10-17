"""add publication retry cooldown

Revision ID: e5b8c2d7f9a3
Revises: d4a9b7c6e8f1
Create Date: 2026-10-17
"""

from alembic import op
import sqlalchemy as sa


revision = "e5b8c2d7f9a3"
down_revision = "d4a9b7c6e8f1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "deployments",
        sa.Column(
            "publication_retry_after",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column("deployments", "publication_retry_after")
