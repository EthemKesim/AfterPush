from unittest.mock import patch
from uuid import uuid4

from afterpush_api.models import Application, Deployment, Project
from afterpush_api.services.deployment_publication_worker import (
    publish_claimed_deployment,
)


def test_published_deployment_is_not_published_again(db_session):
    project = Project(
        name=f"idempotency-test-{uuid4().hex[:8]}",
        repository_url="https://github.com/example/source-code",
    )
    db_session.add(project)
    db_session.flush()

    application = Application(
        project_id=project.id,
        name="idempotency-api",
        image="example/idempotency-api",
        port=3000,
        replicas=2,
    )
    db_session.add(application)
    db_session.flush()

    original_sha = "a" * 40

    deployment = Deployment(
        application_id=application.id,
        environment="dev",
        image_tag="v1",
        revision=1,
        status="published",
        published_commit_sha=original_sha,
    )
    db_session.add(deployment)
    db_session.flush()

    deployment_id = deployment.id

    with (
        patch(
            "afterpush_api.services.deployment_publication_worker.publish_deployment_gitops"
        ) as publisher,
        patch.object(db_session, "rollback") as rollback,
    ):
        result = publish_claimed_deployment(
            db=db_session,
            deployment_id=deployment_id,
            gitops_repository_url="https://example.com/gitops.git",
        )

    assert result == "skipped"
    publisher.assert_not_called()
    rollback.assert_called_once()

    db_session.expire_all()

    saved = db_session.get(Deployment, deployment_id)

    assert saved is not None
    assert saved.status == "published"
    assert saved.published_commit_sha == original_sha
    assert saved.publication_claim_id is None
