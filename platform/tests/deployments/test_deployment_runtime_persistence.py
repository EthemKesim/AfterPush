from uuid import uuid4

from afterpush_api.models import Application, Deployment, Project
from afterpush_api.services.deployment_runtime_persistence import (
    persist_deployment_runtime,
)
from afterpush_api.services.deployment_runtime_verification import (
    DeploymentRuntimeVerification,
)


COMMIT_SHA = "a" * 40


def create_published_deployment(db):
    project = Project(
        name=f"runtime-project-{uuid4().hex[:12]}",
        repository_url="https://example.com/runtime.git",
    )
    db.add(project)
    db.flush()

    application = Application(
        project_id=project.id,
        name="runtime-api",
        image="nginx",
        port=80,
        replicas=1,
    )
    db.add(application)
    db.flush()

    deployment = Deployment(
        application_id=application.id,
        environment="dev",
        image_tag="v1",
        status="published",
        revision=1,
        published_commit_sha=COMMIT_SHA,
    )
    db.add(deployment)
    db.flush()

    return deployment


def healthy_verification():
    return DeploymentRuntimeVerification(
        status="healthy",
        reason="healthy",
        rollout_complete=True,
        revision_verified=True,
    )


def test_persists_healthy_runtime(db_session):
    deployment = create_published_deployment(db_session)

    updated = persist_deployment_runtime(
        db_session,
        deployment_id=deployment.id,
        expected_commit_sha=COMMIT_SHA,
        expected_revision=1,
        verification=healthy_verification(),
    )

    db_session.refresh(deployment)

    assert updated is True
    assert deployment.status == "published"
    assert deployment.runtime_status == "healthy"
    assert deployment.runtime_reason == "healthy"
    assert deployment.runtime_checked_at is not None


def test_rejects_wrong_commit(db_session):
    deployment = create_published_deployment(db_session)

    updated = persist_deployment_runtime(
        db_session,
        deployment_id=deployment.id,
        expected_commit_sha="b" * 40,
        expected_revision=1,
        verification=healthy_verification(),
    )

    db_session.refresh(deployment)

    assert updated is False
    assert deployment.runtime_status == "unverified"


def test_rejects_wrong_revision(db_session):
    deployment = create_published_deployment(db_session)

    updated = persist_deployment_runtime(
        db_session,
        deployment_id=deployment.id,
        expected_commit_sha=COMMIT_SHA,
        expected_revision=2,
        verification=healthy_verification(),
    )

    db_session.refresh(deployment)

    assert updated is False
    assert deployment.runtime_status == "unverified"


def test_rejects_unpublished_deployment(db_session):
    deployment = create_published_deployment(db_session)
    deployment.status = "pending"
    db_session.flush()

    updated = persist_deployment_runtime(
        db_session,
        deployment_id=deployment.id,
        expected_commit_sha=COMMIT_SHA,
        expected_revision=1,
        verification=healthy_verification(),
    )

    db_session.refresh(deployment)

    assert updated is False
    assert deployment.runtime_status == "unverified"


def test_rejects_superseded_deployment(db_session):
    old_deployment = create_published_deployment(db_session)

    newer_deployment = Deployment(
        application_id=old_deployment.application_id,
        environment="dev",
        image_tag="v2",
        status="pending",
        revision=2,
    )
    db_session.add(newer_deployment)
    db_session.flush()

    updated = persist_deployment_runtime(
        db_session,
        deployment_id=old_deployment.id,
        expected_commit_sha=COMMIT_SHA,
        expected_revision=1,
        verification=healthy_verification(),
    )

    db_session.refresh(old_deployment)

    assert updated is False
    assert old_deployment.runtime_status == "unverified"
