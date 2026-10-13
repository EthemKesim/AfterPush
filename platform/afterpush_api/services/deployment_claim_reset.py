from uuid import UUID

from sqlalchemy import update
from sqlalchemy.orm import Session

from afterpush_api.models import Deployment


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
