"""Read-only deployment prerequisite checks."""

from sqlalchemy.orm import Session

from afterpush_api.models import Application, Deployment
from afterpush_api.services.deployment_selection import (
    get_pending_deployment_ids,
)
from afterpush_api.services.namespace_bootstrap_readiness import (
    NamespaceBootstrapNotReady,
    verify_namespace_bootstrap,
)
from afterpush_api.services.gitops_rbac_readiness import (
    GitOpsRBACNotReady,
    verify_gitops_rbac,
)


def inspect_pending_prerequisites(
    *,
    db: Session,
    core_api,
    rbac_api,
    limit: int = 20,
) -> dict[str, int]:
    if limit < 1:
        raise ValueError("limit must be greater than zero")

    if core_api is None or rbac_api is None:
        raise ValueError("Both Kubernetes clients are required")

    deployment_ids = get_pending_deployment_ids(db, limit=limit)

    results = {
        "ready": 0,
        "namespace_not_ready": 0,
        "rbac_not_ready": 0,
        "skipped": 0,
        "errors": 0,
    }

    try:
        for deployment_id in deployment_ids:
            try:
                deployment = db.get(Deployment, deployment_id)

                if deployment is None or deployment.status != "pending":
                    results["skipped"] += 1
                    continue

                application = db.get(
                    Application, deployment.application_id
                )

                if application is None:
                    results["errors"] += 1
                    continue

                target = {
                    "project_id": application.project_id,
                    "application_name": application.name,
                    "environment": deployment.environment,
                }

                try:
                    verify_namespace_bootstrap(
                        core_api=core_api,
                        **target,
                    )
                except NamespaceBootstrapNotReady:
                    results["namespace_not_ready"] += 1
                    continue

                try:
                    verify_gitops_rbac(
                        rbac_api=rbac_api,
                        **target,
                    )
                except GitOpsRBACNotReady:
                    results["rbac_not_ready"] += 1
                    continue

                results["ready"] += 1

            except Exception:
                results["errors"] += 1

    finally:
        # Read-only inspection must not persist DB changes.
        db.rollback()

    return results
