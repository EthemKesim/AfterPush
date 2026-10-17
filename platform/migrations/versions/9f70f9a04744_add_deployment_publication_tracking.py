"""add deployment publication tracking

Revision ID: 9f70f9a04744
Revises: 78faf145ffa3
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "9f70f9a04744"
down_revision: Union[str, Sequence[str], None] = "78faf145ffa3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "deployments",
        sa.Column(
            "publication_claim_id",
            postgresql.UUID(as_uuid=True),
            nullable=True,
        ),
    )

    op.add_column(
        "deployments",
        sa.Column(
            "publication_claimed_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )

    op.add_column(
        "deployments",
        sa.Column(
            "published_commit_sha",
            sa.String(length=64),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column(
        "deployments",
        "published_commit_sha",
    )

    op.drop_column(
        "deployments",
        "publication_claimed_at",
    )

    op.drop_column(
        "deployments",
        "publication_claim_id",
    )
