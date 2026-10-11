
from pathlib import Path
from uuid import UUID

import yaml
from sqlalchemy.orm import Session

from afterpush_api.models import Application, Deployment
from afterpush_api.services.gitops import get_values_path
from afterpush_api.services.locking import (
    gitops_application_lock,
)


def check_deployment_drift(
    db: Session,
    application_id: UUID,
    environment: str,
    gitops_root: Path,
) -> str:
    """
    Compare the latest deployment with local GitOps values.

    Returns:
        "in_sync" when image repository and tag match.
        "drift_detected" when GitOps image differs or is invalid.
        "gitops_missing" when values.yaml does not exist.
        "no_deployment" when no deployment exists.
        "deployment_pending" when the latest revision is pending.
        "deployment_failed" when the latest revision failed.

    The filesystem lock coordinates GitOps reads and writes.
    This function does not modify GitOps values.
    """

    deployment = (
        db.query(Deployment)
        .filter(
            Deployment.application_id == application_id,
            Deployment.environment == environment,
        )
        .order_by(Deployment.revision.desc())
        .first()
    )

    if deployment is None:
        return "no_deployment"

    if deployment.status == "pending":
        return "deployment_pending"

    if deployment.status == "failed":
        return "deployment_failed"

    if deployment.status not in ("running", "succeeded"):
        raise ValueError(
            f"Unsupported deployment status: {deployment.status}"
        )

    application = db.get(Application, application_id)

    if application is None:
        return "no_deployment"

    with gitops_application_lock(
        gitops_root=gitops_root,
        application_name=application.name,
        environment=environment,
    ):
        values_path = get_values_path(
            gitops_root=gitops_root,
            application_name=application.name,
            environment=environment,
        )

        if not values_path.is_file():
            return "gitops_missing"

        with values_path.open("r", encoding="utf-8") as file:
            values = yaml.safe_load(file)

        if not isinstance(values, dict):
            return "drift_detected"

        image = values.get("image")

        if not isinstance(image, dict):
            return "drift_detected"

        if (
            image.get("repository") != application.image
            or image.get("tag") != deployment.image_tag
        ):
            return "drift_detected"

        return "in_sync"
