from uuid import UUID

from sqlalchemy import update
from sqlalchemy.orm import Session

from afterpush_api.models import Deployment


def complete_deployment_publication(
    db: Session,
    deployment_id: UUID,
    claim_id: UUID,
    commit_sha: str,
) -> bool:
    """
    Mark a deployment as published only when the
    provided claim ID still owns the operation.

    The caller must commit the transaction.
    """

    if not commit_sha or len(commit_sha) != 40:
        raise ValueError("A valid Git commit SHA is required.")

    if any(char not in "0123456789abcdefABCDEF" for char in commit_sha):
        raise ValueError("Git commit SHA must be hexadecimal.")

    result = db.execute(
        update(Deployment)
        .where(
            Deployment.id == deployment_id,
            Deployment.status == "publishing",
            Deployment.publication_claim_id == claim_id,
        )
        .values(
            status="published",
            published_commit_sha=commit_sha.lower(),
            publication_claim_id=None,
            publication_claimed_at=None,
        )
        .execution_options(synchronize_session=False)
    )

    return result.rowcount == 1
