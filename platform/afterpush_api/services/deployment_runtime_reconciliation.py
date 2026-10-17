from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload

from afterpush_api.models import Application, Deployment
from afterpush_api.services.deployment_runtime_persistence import (
    persist_deployment_runtime,
)
from afterpush_api.services.deployment_runtime_verification import (
    DeploymentRuntimeVerification,
)
from afterpush_api.services.kubernetes_runtime_observer import (
    KubernetesRuntimeObserver,
    KubernetesRuntimeRequest,
)


def reconcile_deployment_runtimes(
    db: Session,
    *,
    observer: KubernetesRuntimeObserver,
    repository_url: str,
    limit: int = 20,
) -> dict[str, int]:
    """
    Observe the latest published deployment for each
    application/environment and persist its runtime state.

    Kubernetes calls happen outside a database transaction.
    Each result is persisted using a conditional UPDATE.
    """

    if limit < 1:
        raise ValueError("limit must be greater than zero")

    if not repository_url.strip():
        raise ValueError("GitOps repository URL is required")

    latest_revisions = (
        db.query(
            Deployment.application_id.label("application_id"),
            Deployment.environment.label("environment"),
            func.max(Deployment.revision).label("latest_revision"),
        )
        .group_by(
            Deployment.application_id,
            Deployment.environment,
        )
        .subquery()
    )

    deployments = (
        db.query(Deployment)
        .options(joinedload(Deployment.application))
        .join(
            latest_revisions,
            (Deployment.application_id == latest_revisions.c.application_id)
            & (Deployment.environment == latest_revisions.c.environment)
            & (Deployment.revision == latest_revisions.c.latest_revision),
        )
        .filter(
            Deployment.status == "published",
            Deployment.published_commit_sha.isnot(None),
        )
        .order_by(
            Deployment.runtime_checked_at.asc().nullsfirst(),
            Deployment.created_at,
            Deployment.id,
        )
        .limit(limit)
        .all()
    )

    # Snapshot deployment data without modifying the caller's transaction.
    snapshots = [
        (
            deployment.id,
            deployment.application.project_id,
            deployment.application.name,
            deployment.environment,
            deployment.published_commit_sha,
            deployment.revision,
        )
        for deployment in deployments
    ]

    results = {
        "checked": 0,
        "updated": 0,
        "skipped": 0,
        "errors": 0,
    }

    for (
        deployment_id,
        project_id,
        application_name,
        environment,
        commit_sha,
        revision,
    ) in snapshots:
        try:
            verification = observer.observe(
                KubernetesRuntimeRequest(
                    project_id=project_id,
                    application_name=application_name,
                    environment=environment,
                    repository_url=repository_url,
                    expected_commit_sha=commit_sha,
                    expected_revision=revision,
                )
            )
        except Exception:
            _record_observer_error(
                db,
                deployment_id=deployment_id,
                expected_commit_sha=commit_sha,
                expected_revision=revision,
            )
            results["errors"] += 1
            continue

        results["checked"] += 1

        try:
            updated = persist_deployment_runtime(
                db,
                deployment_id=deployment_id,
                expected_commit_sha=commit_sha,
                expected_revision=revision,
                verification=verification,
            )

            if updated:
                results["updated"] += 1
            else:
                results["skipped"] += 1

            db.commit()

        except Exception:
            db.rollback()
            results["errors"] += 1

    return results


def reconcile_deployment_runtimes_managed(
    session_factory,
    *,
    observer: KubernetesRuntimeObserver,
    repository_url: str,
    limit: int = 20,
) -> dict[str, int]:
    """
    Reconcile deployments with independently managed DB sessions.

    No database transaction remains open during Kubernetes observation.
    """

    if limit < 1:
        raise ValueError("limit must be greater than zero")

    if not repository_url.strip():
        raise ValueError("GitOps repository URL is required")

    with session_factory() as db:
        latest_revisions = (
            db.query(
                Deployment.application_id.label("application_id"),
                Deployment.environment.label("environment"),
                func.max(Deployment.revision).label("latest_revision"),
            )
            .group_by(
                Deployment.application_id,
                Deployment.environment,
            )
            .subquery()
        )

        deployments = (
            db.query(Deployment)
            .options(joinedload(Deployment.application))
            .join(
                latest_revisions,
                (Deployment.application_id == latest_revisions.c.application_id)
                & (Deployment.environment == latest_revisions.c.environment)
                & (Deployment.revision == latest_revisions.c.latest_revision),
            )
            .filter(
                Deployment.status == "published",
                Deployment.published_commit_sha.isnot(None),
            )
            .order_by(
                Deployment.runtime_checked_at.asc().nullsfirst(),
                Deployment.created_at,
                Deployment.id,
            )
            .limit(limit)
            .all()
        )

        snapshots = [
            (
                deployment.id,
                deployment.application.project_id,
                deployment.application.name,
                deployment.environment,
                deployment.published_commit_sha,
                deployment.revision,
            )
            for deployment in deployments
        ]

    results = {
        "checked": 0,
        "updated": 0,
        "skipped": 0,
        "errors": 0,
    }

    for (
        deployment_id,
        project_id,
        application_name,
        environment,
        commit_sha,
        revision,
    ) in snapshots:
        try:
            verification = observer.observe(
                KubernetesRuntimeRequest(
                    project_id=project_id,
                    application_name=application_name,
                    environment=environment,
                    repository_url=repository_url,
                    expected_commit_sha=commit_sha,
                    expected_revision=revision,
                )
            )
        except Exception:
            _record_managed_observer_error(
                session_factory,
                deployment_id=deployment_id,
                expected_commit_sha=commit_sha,
                expected_revision=revision,
            )
            results["errors"] += 1
            continue

        results["checked"] += 1

        try:
            with session_factory() as db:
                updated = persist_deployment_runtime(
                    db,
                    deployment_id=deployment_id,
                    expected_commit_sha=commit_sha,
                    expected_revision=revision,
                    verification=verification,
                )
                db.commit()

            if updated:
                results["updated"] += 1
            else:
                results["skipped"] += 1

        except Exception:
            results["errors"] += 1

    return results


def _observer_error_verification() -> DeploymentRuntimeVerification:
    """Return a safe persisted result for an observer failure.

    The exception text may contain cluster or networking details, so it is not
    stored in the deployment record.
    """

    return DeploymentRuntimeVerification(
        status="unverified",
        reason="observer_error",
        rollout_complete=False,
        revision_verified=False,
    )


def _record_observer_error(
    db: Session,
    *,
    deployment_id,
    expected_commit_sha: str,
    expected_revision: int,
) -> None:
    try:
        persist_deployment_runtime(
            db,
            deployment_id=deployment_id,
            expected_commit_sha=expected_commit_sha,
            expected_revision=expected_revision,
            verification=_observer_error_verification(),
        )
        db.commit()
    except Exception:
        db.rollback()


def _record_managed_observer_error(
    session_factory,
    *,
    deployment_id,
    expected_commit_sha: str,
    expected_revision: int,
) -> None:
    with session_factory() as db:
        try:
            persist_deployment_runtime(
                db,
                deployment_id=deployment_id,
                expected_commit_sha=expected_commit_sha,
                expected_revision=expected_revision,
                verification=_observer_error_verification(),
            )
            db.commit()
        except Exception:
            db.rollback()
