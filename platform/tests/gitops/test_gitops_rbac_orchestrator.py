from unittest.mock import Mock
from uuid import uuid4

import pytest

from afterpush_api.services.gitops_rbac_orchestrator import (
    reconcile_gitops_rbac,
)
from afterpush_api.services.gitops_rbac_readiness import (
    GitOpsRBACNotReady,
)


def kwargs():
    return {
        "repository_url": "https://example.com/gitops.git",
        "project_id": uuid4(),
        "application_name": "orders-api",
        "environment": "dev",
        "rbac_api": object(),
    }


def test_ready_rbac_does_not_publish():
    verifier = Mock(return_value=None)
    publisher = Mock()

    result = reconcile_gitops_rbac(
        **kwargs(),
        verifier=verifier,
        publisher=publisher,
    )

    assert result.status == "ready"
    assert result.commit_sha is None
    verifier.assert_called_once()
    publisher.assert_not_called()


def test_missing_rbac_publishes_and_waits():
    verifier = Mock(
        side_effect=GitOpsRBACNotReady("RBAC missing")
    )
    publisher = Mock(return_value="abc123")

    result = reconcile_gitops_rbac(
        **kwargs(),
        verifier=verifier,
        publisher=publisher,
    )

    assert result.status == "waiting"
    assert result.commit_sha == "abc123"
    publisher.assert_called_once()


def test_missing_kubernetes_client_fails_closed():
    values = kwargs()
    values["rbac_api"] = None

    publisher = Mock()

    with pytest.raises(GitOpsRBACNotReady):
        reconcile_gitops_rbac(
            **values,
            publisher=publisher,
        )

    publisher.assert_not_called()


def test_empty_publication_sha_is_rejected():
    verifier = Mock(
        side_effect=GitOpsRBACNotReady("RBAC missing")
    )
    publisher = Mock(return_value=None)

    with pytest.raises(RuntimeError, match="no commit SHA"):
        reconcile_gitops_rbac(
            **kwargs(),
            verifier=verifier,
            publisher=publisher,
        )


def test_unexpected_verification_error_is_not_hidden():
    verifier = Mock(side_effect=ValueError("Invalid identity"))
    publisher = Mock()

    with pytest.raises(ValueError, match="Invalid identity"):
        reconcile_gitops_rbac(
            **kwargs(),
            verifier=verifier,
            publisher=publisher,
        )

    publisher.assert_not_called()
