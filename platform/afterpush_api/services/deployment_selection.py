from uuid import UUID

from sqlalchemy.orm import Session, aliased
from sqlalchemy import select

from afterpush_api.models import Deployment


def get_pending_deployment_ids(
    db: Session,
    limit: int = 20,
) -> list[UUID]:
    """
    Return pending deployments that have no newer revision
    for the same application and environment.

    Older revisions remain in the database but are not
    repeatedly selected by the worker.
    """

    if limit < 1:
        raise ValueError("limit must be greater than zero")

    newer = aliased(Deployment)

    newer_exists = (
        select(newer.id)
        .where(
            newer.application_id == Deployment.application_id,
            newer.environment == Deployment.environment,
            newer.revision > Deployment.revision,
        )
        .exists()
    )

    deployments = (
        db.query(Deployment.id)
        .filter(
            Deployment.status == "pending",
            ~newer_exists,
        )
        .order_by(
            Deployment.created_at.asc(),
            Deployment.id.asc(),
        )
        .limit(limit)
        .all()
    )

    return [deployment_id for (deployment_id,) in deployments]
