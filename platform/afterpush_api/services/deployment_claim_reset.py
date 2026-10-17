from datetime import datetime, timedelta, timezone
from typing import Literal
from uuid import UUID

from sqlalchemy import update
from sqlalchemy.orm import Session

from afterpush_api.models import Deployment


ClaimResetResult = Literal[
    "reset",
    "not_found",
    "claim_changed",
    "not_stale",
]


def reset_abandoned_publication(
    db: Session,
    deployment_id: UUID,
    claim_id: UUID,
    *,
    worker_confirmed_stopped: bool = False,
) -> bool:
    """
    Reset an abandoned publication claim.

    This is an operator-controlled recovery operation,
    not an automatic lease-expiration mechanism.

    The caller must independently establish that the
    previous worker can no longer publish to Git.
    """

    if not worker_confirmed_stopped:
        raise ValueError(
            "The previous worker must be confirmed stopped."
        )

    result = db.execute(
        update(Deployment)
        .where(
            Deployment.id == deployment_id,
            Deployment.status == "publishing",
            Deployment.publication_claim_id == claim_id,
        )
        .values(
            status="pending",
            publication_claim_id=None,
            publication_claimed_at=None,
        )
        .execution_options(synchronize_session=False)
    )

    return result.rowcount == 1


def reset_stale_publication(
    db: Session,
    deployment_id: UUID,
    claim_id: UUID,
    *,
    timeout_minutes: int = 15,
    worker_confirmed_stopped: bool = False,
) -> ClaimResetResult:
    """Safely return a stale, unpublished claim to ``pending``.

    This function does not infer that a worker has stopped merely because
    its claim is old. The caller must explicitly confirm that the worker can
    no longer publish to Git before a reset is allowed.

    The final update repeats every precondition in SQL. This prevents an
    operator from resetting a claim that changed between inspection and
    reset.
    """
    if timeout_minutes < 1:
        raise ValueError("timeout_minutes must be at least 1")

    if not worker_confirmed_stopped:
        raise ValueError(
            "The previous worker must be confirmed stopped."
        )

    cutoff = datetime.now(timezone.utc) - timedelta(
        minutes=timeout_minutes
    )

    deployment = db.get(Deployment, deployment_id)

    if deployment is None:
        return "not_found"

    if (
        deployment.status != "publishing"
        or deployment.publication_claim_id != claim_id
    ):
        return "claim_changed"

    if (
        deployment.publication_claimed_at is None
        or deployment.publication_claimed_at > cutoff
    ):
        return "not_stale"

    result = db.execute(
        update(Deployment)
        .where(
            Deployment.id == deployment_id,
            Deployment.status == "publishing",
            Deployment.publication_claim_id == claim_id,
            Deployment.publication_claimed_at.is_not(None),
            Deployment.publication_claimed_at <= cutoff,
        )
        .values(
            status="pending",
            publication_claim_id=None,
            publication_claimed_at=None,
        )
        .execution_options(synchronize_session=False)
    )

    return "reset" if result.rowcount == 1 else "claim_changed"
