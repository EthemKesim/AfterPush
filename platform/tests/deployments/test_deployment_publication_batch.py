from unittest.mock import patch
from uuid import uuid4

from afterpush_api.models import Application, Deployment, Project
from afterpush_api.services.deployment_publication_worker import (
    process_pending_publications,
)
from afterpush_api.services.deployment_selection import (
    get_pending_deployment_ids,
)


def test_batch_publishes_eligible_deployments(db_session):
    deployment_ids = [uuid4(), uuid4(), uuid4()]

    with (
        patch(
            "afterpush_api.services.deployment_selection.get_pending_deployment_ids",
            return_value=deployment_ids,
        ) as get_pending,
        patch(
            "afterpush_api.services.deployment_publication_worker.publish_claimed_deployment",
            side_effect=["published", "skipped", "published"],
        ) as publish,
    ):
        result = process_pending_publications(
            db=db_session,
            gitops_repository_url="https://example.com/gitops.git",
            limit=3,
        )

    assert result == {
        "published": 2,
        "skipped": 1,
        "deferred": 0,
        "errors": 0,
    }
    assert publish.call_count == 3
    get_pending.assert_called_once_with(
        db=db_session,
        limit=3,
        respect_publication_retry=True,
    )


def test_batch_continues_after_failure(db_session):
    deployment_ids = [uuid4(), uuid4(), uuid4()]

    with (
        patch(
            "afterpush_api.services.deployment_selection.get_pending_deployment_ids",
            return_value=deployment_ids,
        ),
        patch(
            "afterpush_api.services.deployment_publication_worker.publish_claimed_deployment",
            side_effect=[
                RuntimeError("Simulated Git push failure"),
                "published",
                "published",
            ],
        ) as publish,
    ):
        result = process_pending_publications(
            db=db_session,
            gitops_repository_url="https://example.com/gitops.git",
        )

    assert result == {
        "published": 2,
        "skipped": 0,
        "deferred": 0,
        "errors": 1,
    }
    assert publish.call_count == 3


def test_waiting_production_approval_is_not_selected_for_publication(
    db_session,
):
    project = Project(
        name=f"approval-gate-{uuid4().hex[:8]}",
        repository_url="https://example.com/approval-gate.git",
    )
    db_session.add(project)
    db_session.flush()

    application = Application(
        project_id=project.id,
        name="approval-gate-api",
        image="registry.example/approval-gate",
        port=8080,
        replicas=1,
    )
    db_session.add(application)
    db_session.flush()

    waiting_for_approval = Deployment(
        application_id=application.id,
        environment="prod",
        image_tag="v1",
        status="awaiting_approval",
        revision=1,
    )
    db_session.add(waiting_for_approval)
    db_session.flush()

    assert get_pending_deployment_ids(db_session) == []
