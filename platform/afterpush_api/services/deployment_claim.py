from datetime import datetime, timezone
from uuid import UUID, uuid4

from sqlalchemy.orm import Session

from afterpush_api.models import Application, Deployment
from afterpush_api.services.deployment_order import (
    has_newer_deployment,
)


def claim_deployment(
    db: Session,
    deployment_id: UUID,
) -> UUID | None:
    """
    Claim a pending deployment for publication.

    Only one deployment per application/environment
    may be publishing at a time.

    The caller must commit the transaction.
    """

    deployment = db.get(Deployment, deployment_id)

    if deployment is None:
        return None

    application = (
        db.query(Application)
        .filter(Application.id == deployment.application_id)
        .with_for_update()
        .one_or_none()
    )

    if application is None:
        return None

    db.refresh(deployment)

    if deployment.status != "pending":
        return None

    if has_newer_deployment(db, deployment):
        return None

    active_publication = (
        db.query(Deployment.id)
        .filter(
            Deployment.application_id == deployment.application_id,
            Deployment.environment == deployment.environment,
            Deployment.status == "publishing",
            Deployment.id != deployment.id,
        )
        .first()
    )

    if active_publication is not None:
        return None

    claim_id = uuid4()

    deployment.status = "publishing"
    deployment.publication_claim_id = claim_id
    deployment.publication_claimed_at = datetime.now(timezone.utc)

    db.flush()

    return claim_id
