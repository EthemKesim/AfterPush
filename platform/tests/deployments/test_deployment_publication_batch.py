from unittest.mock import patch
from uuid import uuid4

from afterpush_api.services.deployment_publication_worker import (
    process_pending_publications,
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
        "errors": 0,
    }
    assert publish.call_count == 3
    get_pending.assert_called_once_with(db=db_session, limit=3)


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
        "errors": 1,
    }
    assert publish.call_count == 3
