from uuid import uuid4

import pytest

from afterpush_api.models import Application, Deployment, Project
from afterpush_api.services.deployment_claim_reset import (
    reset_abandoned_publication,
)


@pytest.fixture
def publishing_deployment(db_session):
    project = Project(
        name=f"claim-reset-{uuid4().hex[:8]}",
        repository_url="https://github.com/example/source",
    )
    db_session.add(project)
    db_session.flush()

    application = Application(
        project_id=project.id,
        name="reset-api",
        image="example/reset-api",
        port=3000,
        replicas=2,
    )
    db_session.add(application)
    db_session.flush()

    claim_id = uuid4()

    deployment = Deployment(
        application_id=application.id,
        environment="dev",
        image_tag="v1",
        revision=1,
        status="publishing",
        publication_claim_id=claim_id,
    )

    db_session.add(deployment)
    db_session.flush()

    return deployment.id, claim_id


def test_reset_requires_worker_confirmation(
    db_session,
    publishing_deployment,
):
    deployment_id, claim_id = publishing_deployment

    with pytest.raises(ValueError):
        reset_abandoned_publication(
            db=db_session,
            deployment_id=deployment_id,
            claim_id=claim_id,
        )

    db_session.refresh(db_session.get(Deployment, deployment_id))

    deployment = db_session.get(Deployment, deployment_id)
    assert deployment.status == "publishing"
    assert deployment.publication_claim_id == claim_id


def test_reset_accepts_correct_claim(
    db_session,
    publishing_deployment,
):
    deployment_id, claim_id = publishing_deployment

    result = reset_abandoned_publication(
        db=db_session,
        deployment_id=deployment_id,
        claim_id=claim_id,
        worker_confirmed_stopped=True,
    )

    assert result is True

    db_session.flush()
    db_session.expire_all()

    deployment = db_session.get(Deployment, deployment_id)

    assert deployment.status == "pending"
    assert deployment.publication_claim_id is None
    assert deployment.publication_claimed_at is None


def test_reset_rejects_wrong_claim(
    db_session,
    publishing_deployment,
):
    deployment_id, claim_id = publishing_deployment

    result = reset_abandoned_publication(
        db=db_session,
        deployment_id=deployment_id,
        claim_id=uuid4(),
        worker_confirmed_stopped=True,
    )

    assert result is False

    db_session.expire_all()

    deployment = db_session.get(Deployment, deployment_id)

    assert deployment.status == "publishing"
    assert deployment.publication_claim_id == claim_id
