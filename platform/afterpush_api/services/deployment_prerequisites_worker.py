"""Prepare deployment prerequisites independently of workload publication."""

from typing import Callable

from sqlalchemy.orm import Session

from afterpush_api.models import Application, Deployment
from afterpush_api.services.deployment_prerequisites import (
    reconcile_deployment_prerequisites,
)
from afterpush_api.services.deployment_selection import (
    get_pending_deployment_ids,
)
from afterpush_api.services.prerequisites_lock import (
    try_prerequisites_lock,
)
from afterpush_api.services.deployment_prerequisites_eligibility import (
    is_deployment_prerequisites_eligible,
)


def process_pending_prerequisites(
    *,
    db: Session,
    repository_url: str,
    core_api,
    rbac_api,
    limit: int = 20,
    reconciler: Callable = reconcile_deployment_prerequisites,
    lock_engine=None,
) -> dict[str, int]:
    """
    Reconcile namespace and RBAC for pending deployments.

    No deployment claim or status change is performed.
    Publication is handled by a separate worker.
    """

    if not repository_url or not repository_url.strip():
        raise ValueError("GitOps repository URL cannot be empty.")

    if limit < 1:
        raise ValueError("limit must be greater than zero.")

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

    seen = set()

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
                db.rollback()
                results["errors"] += 1
                continue

            identity = (
                application.project_id,
                application.name,
                deployment.environment,
            )

            if identity in seen:
                db.rollback()
                results["skipped"] += 1
                continue

            seen.add(identity)

            # Close the read transaction before GitOps/network work.
            project_id, application_name, environment = identity
            db.rollback()

            if lock_engine is None:
                raise ValueError(
                    "A PostgreSQL lock engine is required."
                )

            with try_prerequisites_lock(
                engine=lock_engine,
                project_id=project_id,
                environment=environment,
            ) as acquired:
                if not acquired:
                    results["skipped"] += 1
                    continue

                # Recheck after acquiring the advisory lock.
                # Close the read transaction before network work.
                try:
                    eligible = is_deployment_prerequisites_eligible(
                        db=db,
                        deployment_id=deployment_id,
                    )
                finally:
                    db.rollback()

                if not eligible:
                    results["skipped"] += 1
                    continue

                result = reconciler(
                    repository_url=repository_url,
                    project_id=project_id,
                    application_name=application_name,
                    environment=environment,
                    core_api=core_api,
                    rbac_api=rbac_api,
                )

                if result.status not in {"ready", "waiting"}:
                    raise RuntimeError(
                        "Unexpected prerequisites reconciliation status."
                    )

                results[result.status] += 1

        except Exception:
            db.rollback()
            results["errors"] += 1

    return results
