from pathlib import Path
from uuid import UUID

from sqlalchemy import exists, select
from sqlalchemy.orm import Session
from sqlalchemy.orm import aliased

from afterpush_api.models import Deployment
from afterpush_api.services.deployment_orchestrator import (
    apply_deployment,
)


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


def process_pending_deployments(
    db: Session,
    gitops_root: Path,
    limit: int = 20,
) -> dict[str, int]:
    """
    Process a batch of pending deployments.

    Each deployment is applied through the existing
    deployment orchestrator.

    A failed deployment does not prevent the remaining
    deployments from being processed.
    """

    deployment_ids = get_pending_deployment_ids(
        db=db,
        limit=limit,
    )

    results = {
        "applied": 0,
        "skipped": 0,
        "not_found": 0,
        "invalid_status": 0,
        "errors": 0,
    }

    for deployment_id in deployment_ids:
        try:
            result = apply_deployment(
                db=db,
                deployment_id=deployment_id,
                gitops_root=gitops_root,
            )

            results[result] += 1

        except Exception:
            db.rollback()
            results["errors"] += 1

    return results
