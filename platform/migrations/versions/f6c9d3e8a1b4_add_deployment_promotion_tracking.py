"""add deployment promotion tracking

Revision ID: f6c9d3e8a1b4
Revises: e5b8c2d7f9a3
Create Date: 2026-10-17
"""

from alembic import op
import sqlalchemy as sa


revision = "f6c9d3e8a1b4"
down_revision = "e5b8c2d7f9a3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "deployments",
        sa.Column("promotion_source_deployment_id", sa.UUID(), nullable=True),
    )
    op.create_foreign_key(
        "fk_deployments_promotion_source",
        "deployments",
        "deployments",
        ["promotion_source_deployment_id"],
        ["id"],
    )
    op.create_index(
        "ix_deployments_promotion_source_deployment_id",
        "deployments",
        ["promotion_source_deployment_id"],
    )
    op.add_column(
        "deployments",
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("deployments", "approved_at")
    op.drop_index(
        "ix_deployments_promotion_source_deployment_id",
        table_name="deployments",
    )
    op.drop_constraint(
        "fk_deployments_promotion_source",
        "deployments",
        type_="foreignkey",
    )
    op.drop_column("deployments", "promotion_source_deployment_id")
