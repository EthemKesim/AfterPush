
"""add deployment revision

Revision ID: 78faf145ffa3
Revises: 64f1bd2880df
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "78faf145ffa3"
down_revision: Union[str, Sequence[str], None] = "64f1bd2880df"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    Add deployment revision numbers.

    Existing deployments receive sequential revisions
    within each application and environment.
    """

    op.add_column(
        "deployments",
        sa.Column(
            "revision",
            sa.Integer(),
            nullable=True,
        ),
    )

    op.execute(
        """
        WITH numbered_deployments AS (
            SELECT
                id,
                ROW_NUMBER() OVER (
                    PARTITION BY application_id, environment
                    ORDER BY created_at ASC, id ASC
                ) AS revision_number
            FROM deployments
        )
        UPDATE deployments AS d
        SET revision = n.revision_number
        FROM numbered_deployments AS n
        WHERE d.id = n.id
        """
    )

    op.alter_column(
        "deployments",
        "revision",
        existing_type=sa.Integer(),
        nullable=False,
    )

    op.create_unique_constraint(
        "uq_deployment_application_environment_revision",
        "deployments",
        [
            "application_id",
            "environment",
            "revision",
        ],
    )


def downgrade() -> None:
    """
    Remove deployment revision numbers.
    """

    op.drop_constraint(
        "uq_deployment_application_environment_revision",
        "deployments",
        type_="unique",
    )

    op.drop_column(
        "deployments",
        "revision",
    )
