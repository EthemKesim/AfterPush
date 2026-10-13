from datetime import datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from afterpush_api.models import Application, Deployment
from afterpush_api.services.deployment_gitops import DeploymentGitOpsSpec
from afterpush_api.services.deployment_publication_completion import (
    complete_deployment_publication,
)
from afterpush_api.services.gitops_publication_verifier import (
    verify_gitops_publication,
)


def get_stale_publications(
    db: Session,
    timeout_minutes: int = 15,
    limit: int = 100,
) -> list[Deployment]:
    """Find expired publication claims without modifying them."""

    if timeout_minutes < 1:
        raise ValueError("timeout_minutes must be at least 1")

    if limit < 1:
        raise ValueError("limit must be at least 1")

    cutoff = datetime.now(timezone.utc) - timedelta(
        minutes=timeout_minutes
    )

    statement = (
        select(Deployment)
        .where(
            Deployment.status == "publishing",
            Deployment.publication_claim_id.is_not(None),
            Deployment.publication_claimed_at.is_not(None),
            Deployment.publication_claimed_at <= cutoff,
        )
        .order_by(
            Deployment.publication_claimed_at.asc(),
            Deployment.id.asc(),
        )
        .limit(limit)
    )

    return list(db.scalars(statement).all())


def recover_published_deployment(
    db: Session,
    deployment_id: UUID,
    gitops_repository_url: str,
    timeout_minutes: int = 15,
) -> str:
    """
    Reconcile an expired publication with GitOps main.

    Only completes a publication when the current GitOps
    values match the claimed deployment.

    Does not reset claims or initiate a Git push.
    """

    if not gitops_repository_url or not gitops_repository_url.strip():
        raise ValueError("GitOps repository URL cannot be empty.")

    if timeout_minutes < 1:
        raise ValueError("timeout_minutes must be at least 1")

    cutoff = datetime.now(timezone.utc) - timedelta(
        minutes=timeout_minutes
    )

    deployment = db.get(Deployment, deployment_id)

    if deployment is None:
        return "not_found"

    if (
        deployment.status != "publishing"
        or deployment.publication_claim_id is None
        or deployment.publication_claimed_at is None
        or deployment.publication_claimed_at > cutoff
    ):
        return "not_eligible"

    application = db.get(Application, deployment.application_id)

    if application is None:
        return "not_found"

    claim_id = deployment.publication_claim_id

    spec = DeploymentGitOpsSpec(
        application_name=application.name,
        environment=deployment.environment,
        image_repository=application.image,
        image_tag=deployment.image_tag,
        port=application.port,
        replicas=application.replicas,
        project_id=application.project_id,
        revision=deployment.revision,
    )

    # Finish the read transaction before the network operation.
    db.rollback()

    verification = verify_gitops_publication(
        repository_url=gitops_repository_url,
        spec=spec,
    )

    if not verification.matches or not verification.commit_sha:
        return "not_published"

    completed = complete_deployment_publication(
        db=db,
        deployment_id=deployment_id,
        claim_id=claim_id,
        commit_sha=verification.commit_sha,
    )

    if not completed:
        db.rollback()
        return "claim_changed"

    db.commit()
    return "recovered"
