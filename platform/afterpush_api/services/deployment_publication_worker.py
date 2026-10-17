from uuid import UUID

from sqlalchemy.orm import Session

from afterpush_api.models import Application, Deployment
from afterpush_api.services.deployment_namespace_gate import (
    NamespaceGateTarget,
    check_deployment_namespace,
)
from afterpush_api.services.namespace_bootstrap_readiness import (
    NamespaceBootstrapNotReady,
)
from afterpush_api.services.gitops_rbac_readiness import (
    GitOpsRBACNotReady,
    verify_gitops_rbac,
)
from afterpush_api.services.deployment_claim import claim_deployment
from afterpush_api.services.deployment_gitops import DeploymentGitOpsSpec
from afterpush_api.services.deployment_publication import (
    publish_deployment_gitops,
)
from afterpush_api.services.deployment_publication_completion import (
    complete_deployment_publication,
)
from afterpush_api.services.deployment_publication_attempt import (
    record_deferred_publication_attempt,
)


class DeploymentPublicationWorkerError(Exception):
    """Raised when a claimed deployment cannot be published."""


def publish_claimed_deployment(
    db: Session,
    deployment_id: UUID,
    gitops_repository_url: str,
    *,
    core_api=None,
    rbac_api=None,
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

    deployment_for_gate = db.get(Deployment, deployment_id)

    if deployment_for_gate is None:
        db.rollback()
        return "skipped"

    if deployment_for_gate.status != "pending":
        db.rollback()
        return "skipped"

    application_for_gate = db.get(
        Application,
        deployment_for_gate.application_id,
    )

    if application_for_gate is None:
        db.rollback()
        raise DeploymentPublicationWorkerError(
            "Deployment application was not found."
        )

    target = NamespaceGateTarget(
        project_id=application_for_gate.project_id,
        application_name=application_for_gate.name,
        environment=deployment_for_gate.environment,
    )

    try:
        check_deployment_namespace(
            target=target,
            core_api=core_api,
        )
        verify_gitops_rbac(
            rbac_api=rbac_api,
            project_id=target.project_id,
            application_name=target.application_name,
            environment=target.environment,
        )
    except (NamespaceBootstrapNotReady, GitOpsRBACNotReady):
        db.rollback()
        record_deferred_publication_attempt(
            db,
            deployment_id=deployment_id,
        )
        db.commit()
        return "deferred"
    except Exception:
        db.rollback()
        raise

    db.rollback()

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
            image_repository=deployment.image_repository,
            image_tag=deployment.image_tag,
            port=deployment.port,
            replicas=deployment.replicas,
            project_id=application.project_id,
            revision=deployment.revision,
        )

        # Recheck namespace readiness before persisting the claim.
        # A failed check rolls back the uncommitted publishing state.
        try:
            check_deployment_namespace(
                target=target,
                core_api=core_api,
            )
            verify_gitops_rbac(
                rbac_api=rbac_api,
                project_id=target.project_id,
                application_name=target.application_name,
                environment=target.environment,
            )
        except (NamespaceBootstrapNotReady, GitOpsRBACNotReady):
            db.rollback()
            record_deferred_publication_attempt(
                db,
                deployment_id=deployment_id,
            )
            db.commit()
            return "deferred"

        # Persist the claim before GitOps publication.
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
    *,
    core_api=None,
    rbac_api=None,
) -> dict[str, int]:
    """
    Publish a batch of eligible pending deployments.

    Each deployment is claimed and published independently.
    A failure does not stop the remaining deployments.

    This function is not yet connected to a scheduler.
    """

    from afterpush_api.services.deployment_selection import (
        get_pending_deployment_ids,
    )

    deployment_ids = get_pending_deployment_ids(
        db=db,
        limit=limit,
        respect_publication_retry=True,
    )

    results = {
        "published": 0,
        "skipped": 0,
        "deferred": 0,
        "errors": 0,
    }

    for deployment_id in deployment_ids:
        try:
            result = publish_claimed_deployment(
                db=db,
                deployment_id=deployment_id,
                gitops_repository_url=gitops_repository_url,
                core_api=core_api,
                rbac_api=rbac_api,
            )

            results[result] += 1

        except Exception:
            db.rollback()
            results["errors"] += 1

    return results
