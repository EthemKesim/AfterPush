
from uuid import UUID

from sqlalchemy import func
from sqlalchemy.orm import Session

from afterpush_api.models import Application, Deployment


def create_versioned_deployment(
    db: Session,
    application_id: UUID,
    environment: str,
    image_tag: str,
) -> Deployment | None:
    """
    Create a deployment with a monotonically increasing revision.

    The application row is locked to serialize concurrent
    deployment creation requests for the same application.
    """

    application = (
        db.query(Application)
        .filter(Application.id == application_id)
        .with_for_update()
        .one_or_none()
    )

    if application is None:
        return None

    latest_revision = (
        db.query(func.max(Deployment.revision))
        .filter(
            Deployment.application_id == application_id,
            Deployment.environment == environment,
        )
        .scalar()
    )

    next_revision = (latest_revision or 0) + 1

    new_deployment = Deployment(
        application_id=application_id,
        environment=environment,
        image_tag=image_tag,
        status="pending",
        revision=next_revision,
    )

    db.add(new_deployment)
    db.flush()

    return new_deployment
