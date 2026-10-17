
from uuid import UUID

from sqlalchemy import func
from sqlalchemy.orm import Session

from afterpush_api.models import Application, Deployment


class DeploymentPromotionNotFound(Exception):
    """Raised when a requested promotion source does not exist."""


class DeploymentPromotionRejected(Exception):
    """Raised when a deployment has not satisfied a promotion gate."""


def create_versioned_deployment(
    db: Session,
    application_id: UUID,
    environment: str,
    image_tag: str,
) -> Deployment | None:
    """
    Create a deployment with a monotonically increasing revision.

    The application row is locked to serialize concurrent
    deployment creation requests for the same application.
    """

    application = (
        db.query(Application)
        .filter(Application.id == application_id)
        .with_for_update()
        .one_or_none()
    )

    if application is None:
        return None

    latest_revision = (
        db.query(func.max(Deployment.revision))
        .filter(
            Deployment.application_id == application_id,
            Deployment.environment == environment,
        )
        .scalar()
    )

    next_revision = (latest_revision or 0) + 1

    new_deployment = Deployment(
        application_id=application_id,
        environment=environment,
        image_repository=application.image,
        image_tag=image_tag,
        port=application.port,
        replicas=application.replicas,
        status="pending",
        revision=next_revision,
    )

    db.add(new_deployment)
    db.flush()

    return new_deployment


def create_promoted_deployment(
    db: Session,
    *,
    source_deployment_id: UUID,
    target_environment: str,
) -> Deployment:
    """Copy a healthy deployment snapshot into its next environment.

    The source deployment, rather than mutable application settings, supplies
    the image, port and replica count.  This keeps a promotion reproducible.
    """

    source = db.get(Deployment, source_deployment_id)
    if source is None:
        raise DeploymentPromotionNotFound()

    application = (
        db.query(Application)
        .filter(Application.id == source.application_id)
        .with_for_update()
        .one_or_none()
    )
    if application is None:
        raise DeploymentPromotionNotFound()

    db.refresh(source)

    expected_source_environment = {
        "staging": "dev",
        "prod": "staging",
    }.get(target_environment)
    if expected_source_environment is None:
        raise DeploymentPromotionRejected("Unsupported promotion target.")

    if source.environment != expected_source_environment:
        raise DeploymentPromotionRejected(
            f"A {target_environment} promotion must start from "
            f"{expected_source_environment}."
        )

    if source.status != "published" or source.runtime_status != "healthy":
        raise DeploymentPromotionRejected(
            "Only a published deployment with healthy runtime status can be promoted."
        )

    latest_revision = (
        db.query(func.max(Deployment.revision))
        .filter(
            Deployment.application_id == application.id,
            Deployment.environment == target_environment,
        )
        .scalar()
    )

    target_status = (
        "awaiting_approval" if target_environment == "prod" else "pending"
    )
    deployment = Deployment(
        application_id=application.id,
        promotion_source_deployment_id=source.id,
        environment=target_environment,
        image_repository=source.image_repository,
        image_tag=source.image_tag,
        port=source.port,
        replicas=source.replicas,
        status=target_status,
        revision=(latest_revision or 0) + 1,
    )
    db.add(deployment)
    db.flush()

    return deployment


def approve_production_promotion(
    db: Session,
    *,
    deployment_id: UUID,
) -> Deployment:
    """Open a waiting production deployment for the publication worker."""

    deployment = db.get(Deployment, deployment_id)
    if deployment is None:
        raise DeploymentPromotionNotFound()

    application = (
        db.query(Application)
        .filter(Application.id == deployment.application_id)
        .with_for_update()
        .one_or_none()
    )
    if application is None:
        raise DeploymentPromotionNotFound()

    db.refresh(deployment)

    if deployment.environment != "prod":
        raise DeploymentPromotionRejected(
            "Only production promotions require approval."
        )
    if deployment.status != "awaiting_approval":
        raise DeploymentPromotionRejected(
            f"Deployment is not awaiting approval: {deployment.status}."
        )

    source = deployment.promotion_source
    if (
        source is None
        or source.environment != "staging"
        or source.status != "published"
        or source.runtime_status != "healthy"
    ):
        raise DeploymentPromotionRejected(
            "The staging source is no longer healthy and cannot be approved."
        )

    from datetime import datetime, timezone

    deployment.status = "pending"
    deployment.approved_at = datetime.now(timezone.utc)
    db.flush()

    return deployment
