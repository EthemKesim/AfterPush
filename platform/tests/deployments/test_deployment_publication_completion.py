from uuid import uuid4

from afterpush_api.models import Application, Deployment, Project
from afterpush_api.services.deployment_publication_completion import (
    complete_deployment_publication,
)


COMMIT_SHA = "a" * 40


def create_claimed_deployment(db):
    project = Project(
        name=f"completion-test-{uuid4().hex[:8]}",
        repository_url="https://github.com/example/project",
    )
    db.add(project)
    db.flush()

    application = Application(
        project_id=project.id,
        name="completion-api",
        image="nginx",
        port=3000,
        replicas=1,
    )
    db.add(application)
    db.flush()

    claim_id = uuid4()

    deployment = Deployment(
        application_id=application.id,
        environment="staging",
        image_tag="v1.0.0",
        status="publishing",
        revision=1,
        publication_claim_id=claim_id,
    )
    db.add(deployment)
    db.flush()

    return deployment, claim_id


def test_correct_claim_completes_publication(db_session):
    deployment, claim_id = create_claimed_deployment(db_session)

    result = complete_deployment_publication(
        db=db_session,
        deployment_id=deployment.id,
        claim_id=claim_id,
        commit_sha=COMMIT_SHA,
    )

    db_session.refresh(deployment)

    assert result is True
    assert deployment.status == "published"
    assert deployment.published_commit_sha == COMMIT_SHA
    assert deployment.publication_claim_id is None


def test_wrong_claim_cannot_complete_publication(db_session):
    deployment, claim_id = create_claimed_deployment(db_session)

    result = complete_deployment_publication(
        db=db_session,
        deployment_id=deployment.id,
        claim_id=uuid4(),
        commit_sha=COMMIT_SHA,
    )

    db_session.refresh(deployment)

    assert result is False
    assert deployment.status == "publishing"
    assert deployment.publication_claim_id == claim_id


def test_same_claim_cannot_complete_twice(db_session):
    deployment, claim_id = create_claimed_deployment(db_session)

    first = complete_deployment_publication(
        db_session,
        deployment.id,
        claim_id,
        COMMIT_SHA,
    )

    second = complete_deployment_publication(
        db_session,
        deployment.id,
        claim_id,
        COMMIT_SHA,
    )

    assert first is True
    assert second is False
