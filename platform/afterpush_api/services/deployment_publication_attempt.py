from datetime import datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy import update
from sqlalchemy.orm import Session

from afterpush_api.models import Deployment


def record_deferred_publication_attempt(
    db: Session,
    *,
    deployment_id: UUID,
    retry_delay: timedelta = timedelta(minutes=1),
) -> bool:
    """Record a safe, retryable publication deferral.

    The caller must commit the transaction.  This timestamp lets batch
    selection give untried pending deployments a chance before retrying an
    unchanged prerequisite failure.
    """

    if not isinstance(retry_delay, timedelta) or retry_delay <= timedelta():
        raise ValueError("retry_delay must be a positive timedelta")

    now = datetime.now(timezone.utc)

    result = db.execute(
        update(Deployment)
        .where(
            Deployment.id == deployment_id,
            Deployment.status == "pending",
        )
        .values(
            publication_checked_at=now,
            publication_retry_after=now + retry_delay,
        )
        .execution_options(synchronize_session=False)
    )

    return result.rowcount == 1
