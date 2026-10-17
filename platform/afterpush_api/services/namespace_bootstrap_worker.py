"""Reconcile namespace bootstrap for pending deployments."""

from uuid import UUID

from sqlalchemy.orm import Session

from afterpush_api.models import Application, Deployment
from afterpush_api.services.deployment_selection import (
    get_pending_deployment_ids,
)
from afterpush_api.services.namespace_bootstrap_orchestrator import (
    reconcile_namespace_bootstrap,
)
from afterpush_api.services.namespace_bootstrap_publication import (
    NamespaceBootstrapPublicationSpec,
)


def reconcile_pending_namespace_bootstraps(
    *,
    db: Session,
    repository_url: str,
    core_api,
    limit: int = 20,
) -> dict[str, int]:
    """
    Reconcile namespace bootstrap for pending deployments.

    Does not claim deployments, change deployment statuses,
    or publish application workloads.
    """

    if limit < 1:
        raise ValueError("limit must be greater than zero.")

    if not repository_url or not repository_url.strip():
        raise ValueError("GitOps repository URL cannot be empty.")

    if core_api is None:
        raise ValueError("Kubernetes CoreV1Api is required.")

    deployment_ids = get_pending_deployment_ids(
        db=db,
        limit=limit,
    )

    results = {
        "ready": 0,
        "waiting": 0,
        "skipped": 0,
        "errors": 0,
    }

    for deployment_id in deployment_ids:
        try:
            deployment = db.get(Deployment, deployment_id)

            if deployment is None or deployment.status != "pending":
                db.rollback()
                results["skipped"] += 1
                continue

            application = db.get(
                Application,
                deployment.application_id,
            )

            if application is None:
                raise RuntimeError(
                    f"Application not found for deployment {deployment_id}."
                )

            spec = NamespaceBootstrapPublicationSpec(
                project_id=application.project_id,
                application_name=application.name,
                environment=deployment.environment,
            )

            db.rollback()

            result = reconcile_namespace_bootstrap(
                repository_url=repository_url,
                spec=spec,
                core_api=core_api,
            )

            results[result.status] += 1

        except Exception:
            db.rollback()
            results["errors"] += 1

    return results
