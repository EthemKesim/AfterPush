from types import SimpleNamespace
from unittest.mock import MagicMock, patch
from uuid import uuid4

from afterpush_api.services.deployment_publication_worker import (
    publish_claimed_deployment,
)


def test_missing_kubernetes_client_does_not_claim_or_publish():
    deployment_id = uuid4()
    application_id = uuid4()
    project_id = uuid4()

    deployment = SimpleNamespace(
        id=deployment_id,
        application_id=application_id,
        environment="dev",
        status="pending",
    )

    application = SimpleNamespace(
        id=application_id,
        project_id=project_id,
        name="payment-api",
    )

    db = MagicMock()

    def get_model(model, identifier):
        if identifier == deployment_id:
            return deployment
        if identifier == application_id:
            return application
        return None

    db.get.side_effect = get_model

    with (
        patch(
            "afterpush_api.services.deployment_publication_worker."
            "claim_deployment"
        ) as claim,
        patch(
            "afterpush_api.services.deployment_publication_worker."
            "publish_deployment_gitops"
        ) as publish,
        patch(
            "afterpush_api.services.deployment_publication_worker."
            "record_deferred_publication_attempt",
            return_value=True,
        ) as record_attempt,
    ):
        result = publish_claimed_deployment(
            db=db,
            deployment_id=deployment_id,
            gitops_repository_url="https://example.com/gitops.git",
            core_api=None,
        )

    assert result == "deferred"
    claim.assert_not_called()
    publish.assert_not_called()
    record_attempt.assert_called_once_with(db, deployment_id=deployment_id)
    db.commit.assert_called_once()
