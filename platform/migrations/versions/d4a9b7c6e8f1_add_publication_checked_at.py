"""add publication checked timestamp

Revision ID: d4a9b7c6e8f1
Revises: c3d8e1f2a4b5
Create Date: 2026-10-17
"""

from alembic import op
import sqlalchemy as sa


revision = "d4a9b7c6e8f1"
down_revision = "c3d8e1f2a4b5"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "deployments",
        sa.Column(
            "publication_checked_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column("deployments", "publication_checked_at")
