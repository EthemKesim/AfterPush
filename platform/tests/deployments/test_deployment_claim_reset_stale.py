from datetime import datetime, timedelta, timezone
from uuid import uuid4

from afterpush_api.models import Application, Deployment, Project
from afterpush_api.services.deployment_claim_reset import (
    reset_stale_publication,
)


def create_publishing_deployment(db_session, *, claimed_at):
    project = Project(
        name=f"stale-claim-{uuid4().hex[:8]}",
        repository_url="https://example.com/stale-claim.git",
    )
    db_session.add(project)
    db_session.flush()

    application = Application(
        project_id=project.id,
        name="stale-claim-api",
        image="example/stale-claim-api",
        port=3000,
        replicas=2,
    )
    db_session.add(application)
    db_session.flush()

    claim_id = uuid4()
    deployment = Deployment(
        application_id=application.id,
        environment="dev",
        image_repository=application.image,
        image_tag="v1",
        port=application.port,
        replicas=application.replicas,
        revision=1,
        status="publishing",
        publication_claim_id=claim_id,
        publication_claimed_at=claimed_at,
    )
    db_session.add(deployment)
    db_session.flush()
    return deployment, claim_id


def test_stale_claim_reset_returns_deployment_to_pending(db_session):
    deployment, claim_id = create_publishing_deployment(
        db_session,
        claimed_at=datetime.now(timezone.utc) - timedelta(minutes=30),
    )

    result = reset_stale_publication(
        db_session,
        deployment.id,
        claim_id,
        timeout_minutes=15,
        worker_confirmed_stopped=True,
    )

    assert result == "reset"
    db_session.flush()
    db_session.refresh(deployment)
    assert deployment.status == "pending"
    assert deployment.publication_claim_id is None
    assert deployment.publication_claimed_at is None


def test_recent_claim_is_not_reset_even_with_operator_confirmation(db_session):
    deployment, claim_id = create_publishing_deployment(
        db_session,
        claimed_at=datetime.now(timezone.utc) - timedelta(minutes=2),
    )

    result = reset_stale_publication(
        db_session,
        deployment.id,
        claim_id,
        timeout_minutes=15,
        worker_confirmed_stopped=True,
    )

    assert result == "not_stale"
    db_session.refresh(deployment)
    assert deployment.status == "publishing"
    assert deployment.publication_claim_id == claim_id


def test_changed_claim_is_not_reset(db_session):
    deployment, claim_id = create_publishing_deployment(
        db_session,
        claimed_at=datetime.now(timezone.utc) - timedelta(minutes=30),
    )

    result = reset_stale_publication(
        db_session,
        deployment.id,
        uuid4(),
        timeout_minutes=15,
        worker_confirmed_stopped=True,
    )

    assert result == "claim_changed"
    db_session.refresh(deployment)
    assert deployment.status == "publishing"
    assert deployment.publication_claim_id == claim_id
