from uuid import UUID

from sqlalchemy.orm import Session

from afterpush_api.models import Deployment
from afterpush_api.services.deployment_order import (
    has_newer_deployment,
)


class DeploymentPublicationRejected(Exception):
    """Raised when a deployment is not eligible for publication."""


def validate_deployment_for_publication(
    db: Session,
    deployment_id: UUID,
) -> Deployment:
    """
    Validate that a deployment is pending and has
    no newer revision for its application/environment.

    This is a preliminary eligibility check, not a
    concurrency lock or publication claim.
    """

    deployment = db.get(Deployment, deployment_id)

    if deployment is None:
        raise DeploymentPublicationRejected(
            "Deployment not found."
        )

    if deployment.status != "pending":
        raise DeploymentPublicationRejected(
            f"Deployment is not pending: {deployment.status}"
        )

    if has_newer_deployment(db, deployment):
        raise DeploymentPublicationRejected(
            "A newer deployment revision already exists."
        )

    return deployment
