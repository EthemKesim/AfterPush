from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import exists, select, update
from sqlalchemy.orm import Session

from afterpush_api.models import Application, Deployment
from afterpush_api.services.deployment_runtime_verification import (
    DeploymentRuntimeVerification,
)


def persist_deployment_runtime(
    db: Session,
    *,
    deployment_id: UUID,
    expected_commit_sha: str,
    expected_revision: int,
    verification: DeploymentRuntimeVerification,
) -> bool:
    """
    Persist a runtime observation only if the deployment
    still matches the revision and Git commit that were observed.

    The caller must commit the transaction.
    """

    if not expected_commit_sha or len(expected_commit_sha) != 40:
        raise ValueError("A valid Git commit SHA is required.")

    if any(char not in "0123456789abcdefABCDEF" for char in expected_commit_sha):
        raise ValueError("Git commit SHA must be hexadecimal.")

    if type(expected_revision) is not int or expected_revision < 1:
        raise ValueError("Invalid expected revision.")

    allowed_statuses = {
        "healthy",
        "progressing",
        "degraded",
        "out_of_sync",
        "revision_mismatch",
        "unverified",
    }

    if verification.status not in allowed_statuses:
        raise ValueError("Invalid runtime status.")

    # Resolve the parent application without locking the deployment row.
    # Both deployment creation and runtime persistence acquire the
    # Application lock first, keeping lock ordering consistent.
    application_id = db.execute(
        select(Deployment.application_id).where(
            Deployment.id == deployment_id
        )
    ).scalar_one_or_none()

    if application_id is None:
        return False

    application = (
        db.query(Application)
        .filter(Application.id == application_id)
        .with_for_update()
        .one_or_none()
    )

    if application is None:
        return False

    newer = Deployment.__table__.alias("newer_deployment")

    newer_deployment = (
        select(newer.c.id)
        .where(
            newer.c.application_id == Deployment.application_id,
            newer.c.environment == Deployment.environment,
            newer.c.revision > expected_revision,
        )
    )

    result = db.execute(
        update(Deployment)
        .where(
            Deployment.id == deployment_id,
            Deployment.status == "published",
            Deployment.revision == expected_revision,
            Deployment.published_commit_sha == expected_commit_sha.lower(),
            ~exists(newer_deployment),
        )
        .values(
            runtime_status=verification.status,
            runtime_reason=verification.reason[:255],
            runtime_checked_at=datetime.now(timezone.utc),
        )
        .execution_options(synchronize_session=False)
    )

    return result.rowcount == 1
