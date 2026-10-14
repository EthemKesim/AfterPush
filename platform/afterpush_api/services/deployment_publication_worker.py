from uuid import UUID

from sqlalchemy.orm import Session

from afterpush_api.models import Application, Deployment
from afterpush_api.services.deployment_claim import claim_deployment
from afterpush_api.services.deployment_gitops import DeploymentGitOpsSpec
from afterpush_api.services.deployment_publication import (
    publish_deployment_gitops,
)
from afterpush_api.services.deployment_publication_completion import (
    complete_deployment_publication,
)


class DeploymentPublicationWorkerError(Exception):
    """Raised when a claimed deployment cannot be published."""


def publish_claimed_deployment(
    db: Session,
    deployment_id: UUID,
    gitops_repository_url: str,
) -> str:
    """
    Claim, publish and complete a deployment.

    The GitOps repository is explicitly provided and must
    not be confused with the project's source repository.

    Returns:
        "published" when GitOps publication is completed.
        "skipped" when the deployment cannot be claimed.

    If publication fails after claiming, the deployment remains
    in 'publishing' until a recovery mechanism handles it.
    """

    if not gitops_repository_url or not gitops_repository_url.strip():
        raise ValueError("GitOps repository URL cannot be empty.")

    try:
        claim_id = claim_deployment(db, deployment_id)

        if claim_id is None:
            db.rollback()
            return "skipped"

        deployment = db.get(Deployment, deployment_id)
        application = db.get(Application, deployment.application_id)

        if application is None:
            raise DeploymentPublicationWorkerError(
                "Deployment application was not found."
            )

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

        # Persist the claim before performing network operations.
        db.commit()

    except Exception:
        db.rollback()
        raise

    try:
        commit_sha = publish_deployment_gitops(
            repository_url=gitops_repository_url,
            spec=spec,
        )

    except Exception as exc:
        db.rollback()
        raise DeploymentPublicationWorkerError(
            f"GitOps publication failed for deployment {deployment_id}"
        ) from exc

    if not commit_sha:
        raise DeploymentPublicationWorkerError(
            "GitOps publisher returned no commit SHA."
        )

    try:
        completed = complete_deployment_publication(
            db=db,
            deployment_id=deployment_id,
            claim_id=claim_id,
            commit_sha=commit_sha,
        )

        if not completed:
            raise DeploymentPublicationWorkerError(
                "Publication claim was no longer valid."
            )

        db.commit()

    except Exception:
        db.rollback()
        raise

    return "published"


def process_pending_publications(
    db: Session,
    gitops_repository_url: str,
    limit: int = 20,
) -> dict[str, int]:
    """
    Publish a batch of eligible pending deployments.

    Each deployment is claimed and published independently.
    A failure does not stop the remaining deployments.

    This function is not yet connected to a scheduler.
    """

    from afterpush_api.services.deployment_worker import (
        get_pending_deployment_ids,
    )

    deployment_ids = get_pending_deployment_ids(
        db=db,
        limit=limit,
    )

    results = {
        "published": 0,
        "skipped": 0,
        "errors": 0,
    }

    for deployment_id in deployment_ids:
        try:
            result = publish_claimed_deployment(
                db=db,
                deployment_id=deployment_id,
                gitops_repository_url=gitops_repository_url,
            )

            results[result] += 1

        except Exception:
            db.rollback()
            results["errors"] += 1

    return results
