"""add immutable deployment specification snapshot

Revision ID: c3d8e1f2a4b5
Revises: b7e2c6a49031
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "c3d8e1f2a4b5"
down_revision: Union[str, Sequence[str], None] = "b7e2c6a49031"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Snapshot the application values that define a deployment."""
    op.add_column(
        "deployments",
        sa.Column("image_repository", sa.String(length=500), nullable=True),
    )
    op.add_column(
        "deployments",
        sa.Column("port", sa.Integer(), nullable=True),
    )
    op.add_column(
        "deployments",
        sa.Column("replicas", sa.Integer(), nullable=True),
    )

    op.execute(
        """
        UPDATE deployments AS deployment
        SET
            image_repository = application.image,
            port = application.port,
            replicas = application.replicas
        FROM applications AS application
        WHERE application.id = deployment.application_id
        """
    )

    op.alter_column("deployments", "image_repository", nullable=False)
    op.alter_column("deployments", "port", nullable=False)
    op.alter_column("deployments", "replicas", nullable=False)


def downgrade() -> None:
    op.drop_column("deployments", "replicas")
    op.drop_column("deployments", "port")
    op.drop_column("deployments", "image_repository")
