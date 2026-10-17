"""Check whether a deployment still needs prerequisites."""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from afterpush_api.models import Deployment


def is_deployment_prerequisites_eligible(
    *,
    db: Session,
    deployment_id: UUID,
) -> bool:
    """
    Return True only for a pending deployment without a newer revision.

    This is a read-only check and does not claim the deployment.
    """

    deployment = db.get(Deployment, deployment_id)

    if deployment is None or deployment.status != "pending":
        return False

    newer_exists = (
        select(Deployment.id)
        .where(
            Deployment.application_id == deployment.application_id,
            Deployment.environment == deployment.environment,
            Deployment.revision > deployment.revision,
        )
        .limit(1)
    )

    return db.execute(newer_exists).first() is None
