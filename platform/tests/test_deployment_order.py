
from uuid import uuid4

from sqlalchemy.orm import Session

from afterpush_api.models import Application, Deployment, Project
from afterpush_api.services.deployment_order import (
    has_newer_deployment,
)


def create_project_and_application(db: Session):
    project = Project(
        name=f"project-{uuid4().hex[:8]}",
        repository_url="https://github.com/example/project",
    )

    db.add(project)
    db.flush()

    application = Application(
        project_id=project.id,
        name="payment-service",
        image="nginx",
        port=3000,
        replicas=2,
    )

    db.add(application)
    db.flush()

    return application


def create_deployment(
    db: Session,
    application_id,
    environment,
    revision,
):
    deployment = Deployment(
        application_id=application_id,
        environment=environment,
        image_tag="v1.0.0",
        status="pending",
        revision=revision,
    )

    db.add(deployment)
    db.flush()

    return deployment


def test_detects_newer_deployment(db_session):
    application = create_project_and_application(db_session)

    older = create_deployment(
        db_session,
        application.id,
        "staging",
        revision=1,
    )

    create_deployment(
        db_session,
        application.id,
        "staging",
        revision=2,
    )

    assert has_newer_deployment(db_session, older) is True


def test_ignores_other_environment(db_session):
    application = create_project_and_application(db_session)

    staging = create_deployment(
        db_session,
        application.id,
        "staging",
        revision=1,
    )

    create_deployment(
        db_session,
        application.id,
        "prod",
        revision=2,
    )

    assert has_newer_deployment(db_session, staging) is False


def test_ignores_other_application(db_session):
    application = create_project_and_application(db_session)

    second_application = Application(
        project_id=application.project_id,
        name="second-service",
        image="nginx",
        port=3001,
        replicas=1,
    )

    db_session.add(second_application)
    db_session.flush()

    first_deployment = create_deployment(
        db_session,
        application.id,
        "staging",
        revision=1,
    )

    create_deployment(
        db_session,
        second_application.id,
        "staging",
        revision=2,
    )

    assert has_newer_deployment(
        db_session,
        first_deployment,
    ) is False


def test_single_deployment_has_no_newer(db_session):
    application = create_project_and_application(db_session)

    deployment = create_deployment(
        db_session,
        application.id,
        "staging",
        revision=1,
    )

    assert has_newer_deployment(
        db_session,
        deployment,
    ) is False


def test_older_timestamp_does_not_override_revision(db_session):
    """
    A deployment with a higher revision is newer
    regardless of timestamp ordering.
    """

    application = create_project_and_application(db_session)

    older = create_deployment(
        db_session,
        application.id,
        "staging",
        revision=1,
    )

    newer = create_deployment(
        db_session,
        application.id,
        "staging",
        revision=2,
    )

    assert has_newer_deployment(db_session, older) is True
    assert has_newer_deployment(db_session, newer) is False
