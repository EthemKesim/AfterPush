from uuid import uuid4

from afterpush_api.models import Application, Deployment, Project
from afterpush_api.services.deployment_prerequisites_eligibility import (
    is_deployment_prerequisites_eligible,
)


def create_deployment(db_session, *, revision, status="pending", application=None):
    if application is None:
        project = Project(
            name=f"eligibility-{uuid4().hex[:8]}",
            repository_url="https://example.com/source.git",
        )
        db_session.add(project)
        db_session.flush()

        application = Application(
            project_id=project.id,
            name="eligibility-api",
            image="example/eligibility-api",
            port=3000,
            replicas=2,
        )
        db_session.add(application)
        db_session.flush()

    deployment = Deployment(
        application_id=application.id,
        environment="dev",
        image_tag=f"v{revision}",
        status=status,
        revision=revision,
    )

    db_session.add(deployment)
    db_session.flush()

    return deployment, application


def test_latest_pending_deployment_is_eligible(db_session):
    deployment, _ = create_deployment(
        db_session,
        revision=1,
    )

    assert is_deployment_prerequisites_eligible(
        db=db_session,
        deployment_id=deployment.id,
    ) is True


def test_older_revision_is_not_eligible(db_session):
    older, application = create_deployment(
        db_session,
        revision=1,
    )

    create_deployment(
        db_session,
        revision=2,
        application=application,
    )

    assert is_deployment_prerequisites_eligible(
        db=db_session,
        deployment_id=older.id,
    ) is False


def test_non_pending_deployment_is_not_eligible(db_session):
    deployment, _ = create_deployment(
        db_session,
        revision=1,
        status="published",
    )

    assert is_deployment_prerequisites_eligible(
        db=db_session,
        deployment_id=deployment.id,
    ) is False
