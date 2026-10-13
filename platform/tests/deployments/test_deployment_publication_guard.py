from uuid import uuid4

import pytest

from afterpush_api.models import Application, Deployment, Project
from afterpush_api.services.deployment_publication_guard import (
    DeploymentPublicationRejected,
    validate_deployment_for_publication,
)


def create_application(db):
    project = Project(
        name=f"guard-test-{uuid4().hex[:8]}",
        repository_url="https://github.com/example/project",
    )
    db.add(project)
    db.flush()

    application = Application(
        project_id=project.id,
        name="payment-api",
        image="nginx",
        port=3000,
        replicas=2,
    )
    db.add(application)
    db.flush()

    return application


def create_deployment(db, application, revision, status="pending"):
    deployment = Deployment(
        application_id=application.id,
        environment="staging",
        image_tag=f"v{revision}.0.0",
        status=status,
        revision=revision,
    )
    db.add(deployment)
    db.flush()

    return deployment


def test_accepts_latest_pending_deployment(db_session):
    application = create_application(db_session)
    deployment = create_deployment(db_session, application, 1)

    result = validate_deployment_for_publication(
        db_session,
        deployment.id,
    )

    assert result.id == deployment.id


def test_rejects_outdated_revision(db_session):
    application = create_application(db_session)

    old = create_deployment(db_session, application, 1)
    create_deployment(db_session, application, 2)

    with pytest.raises(
        DeploymentPublicationRejected,
        match="newer deployment revision",
    ):
        validate_deployment_for_publication(
            db_session,
            old.id,
        )


def test_rejects_non_pending_deployment(db_session):
    application = create_application(db_session)

    deployment = create_deployment(
        db_session,
        application,
        1,
        status="running",
    )

    with pytest.raises(
        DeploymentPublicationRejected,
        match="not pending",
    ):
        validate_deployment_for_publication(
            db_session,
            deployment.id,
        )
