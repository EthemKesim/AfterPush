from types import SimpleNamespace
from unittest.mock import Mock, patch
from uuid import uuid4

import pytest

from afterpush_api.services.namespace_bootstrap_worker import (
    reconcile_pending_namespace_bootstraps,
)


MODULE = "afterpush_api.services.namespace_bootstrap_worker"


def test_reconciles_pending_deployments():
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

    db = Mock()
    db.get.side_effect = [deployment, application]

    with (
        patch(
            f"{MODULE}.get_pending_deployment_ids",
            return_value=[deployment_id],
        ),
        patch(
            f"{MODULE}.reconcile_namespace_bootstrap",
            return_value=SimpleNamespace(status="waiting"),
        ) as reconcile,
    ):
        result = reconcile_pending_namespace_bootstraps(
            db=db,
            repository_url="test-repository",
            core_api=object(),
        )

    assert result == {
        "ready": 0,
        "waiting": 1,
        "skipped": 0,
        "errors": 0,
    }

    reconcile.assert_called_once()
    spec = reconcile.call_args.kwargs["spec"]

    assert spec.project_id == project_id
    assert spec.application_name == "payment-api"
    assert spec.environment == "dev"


def test_skips_non_pending_deployment():
    deployment_id = uuid4()

    db = Mock()
    db.get.return_value = SimpleNamespace(status="published")

    with (
        patch(
            f"{MODULE}.get_pending_deployment_ids",
            return_value=[deployment_id],
        ),
        patch(
            f"{MODULE}.reconcile_namespace_bootstrap",
        ) as reconcile,
    ):
        result = reconcile_pending_namespace_bootstraps(
            db=db,
            repository_url="test-repository",
            core_api=object(),
        )

    assert result["skipped"] == 1
    reconcile.assert_not_called()


def test_continues_after_reconciliation_error():
    deployment_ids = [uuid4(), uuid4()]

    deployments = [
        SimpleNamespace(
            id=deployment_ids[0],
            application_id=uuid4(),
            environment="dev",
            status="pending",
        ),
        SimpleNamespace(
            id=deployment_ids[1],
            application_id=uuid4(),
            environment="staging",
            status="pending",
        ),
    ]

    applications = [
        SimpleNamespace(project_id=uuid4(), name="first-api"),
        SimpleNamespace(project_id=uuid4(), name="second-api"),
    ]

    db = Mock()
    db.get.side_effect = [
        deployments[0],
        applications[0],
        deployments[1],
        applications[1],
    ]

    with (
        patch(
            f"{MODULE}.get_pending_deployment_ids",
            return_value=deployment_ids,
        ),
        patch(
            f"{MODULE}.reconcile_namespace_bootstrap",
            side_effect=[
                RuntimeError("Simulated GitOps failure"),
                SimpleNamespace(status="ready"),
            ],
        ),
    ):
        result = reconcile_pending_namespace_bootstraps(
            db=db,
            repository_url="test-repository",
            core_api=object(),
        )

    assert result == {
        "ready": 1,
        "waiting": 0,
        "skipped": 0,
        "errors": 1,
    }


@pytest.mark.parametrize(
    "limit",
    [0, -1],
)
def test_rejects_invalid_limit(limit):
    with pytest.raises(ValueError, match="limit"):
        reconcile_pending_namespace_bootstraps(
            db=Mock(),
            repository_url="test-repository",
            core_api=object(),
            limit=limit,
        )


def test_missing_kubernetes_client_fails_closed():
    with pytest.raises(ValueError, match="CoreV1Api"):
        reconcile_pending_namespace_bootstraps(
            db=Mock(),
            repository_url="test-repository",
            core_api=None,
        )


def test_empty_repository_url_is_rejected():
    with pytest.raises(ValueError, match="repository URL"):
        reconcile_pending_namespace_bootstraps(
            db=Mock(),
            repository_url="",
            core_api=object(),
        )
