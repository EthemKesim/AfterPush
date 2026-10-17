from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy.orm import Session, aliased
from sqlalchemy import or_, select

from afterpush_api.models import Deployment


def get_pending_deployment_ids(
    db: Session,
    limit: int = 20,
    *,
    respect_publication_retry: bool = False,
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

    filters = [
        Deployment.status == "pending",
        ~newer_exists,
    ]

    if respect_publication_retry:
        now = datetime.now(timezone.utc)
        filters.append(
            or_(
                Deployment.publication_retry_after.is_(None),
                Deployment.publication_retry_after <= now,
            )
        )

    deployments = (
        db.query(Deployment.id)
        .filter(*filters)
        .order_by(
            Deployment.publication_checked_at.asc().nullsfirst(),
            Deployment.created_at.asc(),
            Deployment.id.asc(),
        )
        .limit(limit)
        .all()
    )

    return [deployment_id for (deployment_id,) in deployments]
