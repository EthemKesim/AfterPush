
from pathlib import Path
from uuid import UUID

from sqlalchemy.orm import Session

from afterpush_api.models import Application, Deployment
from afterpush_api.services.deployment_order import (
    has_newer_deployment,
)
from afterpush_api.services.sync import (
    sync_gitops_application,
)


def apply_deployment(
    db: Session,
    deployment_id: UUID,
    gitops_root: Path,
) -> str:
    """
    Apply a pending deployment to the local GitOps configuration.

    Returns:
        "applied"
        "skipped"
        "not_found"
        "invalid_status"

    Transaction ownership:
        Commits or rolls back the supplied session.

    Caller must not have unrelated uncommitted changes.
    """

    try:
        deployment = db.get(Deployment, deployment_id)

        if deployment is None:
            db.rollback()
            return "not_found"

        application = (
            db.query(Application)
            .filter(
                Application.id == deployment.application_id
            )
            .with_for_update()
            .one_or_none()
        )

        if application is None:
            db.rollback()
            return "not_found"

        db.refresh(deployment)

        if deployment.status != "pending":
            db.rollback()
            return "invalid_status"

        if has_newer_deployment(db, deployment):
            db.rollback()
            return "skipped"

        sync_gitops_application(
            gitops_root=gitops_root,
            application_name=application.name,
            environment=deployment.environment,
            image_repository=application.image,
            image_tag=deployment.image_tag,
            port=application.port,
            replicas=application.replicas,
            project_id=application.project_id,
        )

        deployment.status = "running"
        db.commit()

        return "applied"

    except Exception:
        db.rollback()
        raise
