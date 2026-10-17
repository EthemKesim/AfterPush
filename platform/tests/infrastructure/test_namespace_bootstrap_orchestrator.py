from unittest.mock import Mock
from uuid import UUID

import pytest

from afterpush_api.services.namespace_bootstrap_orchestrator import (
    reconcile_namespace_bootstrap,
)
from afterpush_api.services.namespace_bootstrap_publication import (
    NamespaceBootstrapPublicationSpec,
)
from afterpush_api.services.namespace_bootstrap_readiness import (
    NamespaceBootstrapNotReady,
)


PROJECT_ID = UUID("12471cf9-11d4-4089-ad0d-2c4b777fc227")


def make_spec():
    return NamespaceBootstrapPublicationSpec(
        project_id=PROJECT_ID,
        application_name="payment-api",
        environment="dev",
    )


def reconcile(verifier, publisher, core_api=None):
    return reconcile_namespace_bootstrap(
        repository_url="test-gitops-repository",
        spec=make_spec(),
        core_api=core_api if core_api is not None else object(),
        verifier=verifier,
        publisher=publisher,
    )


def test_ready_namespace_does_not_publish():
    namespace = f"ap-dev-{PROJECT_ID}"

    verifier = Mock(return_value=namespace)
    publisher = Mock()

    result = reconcile(verifier, publisher)

    assert result.status == "ready"
    assert result.namespace == namespace
    assert result.commit_sha is None

    verifier.assert_called_once()
    publisher.assert_not_called()


def test_missing_namespace_publishes_bootstrap():
    verifier = Mock(
        side_effect=NamespaceBootstrapNotReady(
            "Namespace is missing."
        )
    )
    publisher = Mock(return_value="bootstrap-commit-sha")

    result = reconcile(verifier, publisher)

    assert result.status == "waiting"
    assert result.namespace is None
    assert result.commit_sha == "bootstrap-commit-sha"

    publisher.assert_called_once_with(
        repository_url="test-gitops-repository",
        spec=make_spec(),
    )


def test_weakened_policy_requests_bootstrap():
    verifier = Mock(
        side_effect=NamespaceBootstrapNotReady(
            "Namespace security label mismatch."
        )
    )
    publisher = Mock(return_value="bootstrap-commit-sha")

    result = reconcile(verifier, publisher)

    assert result.status == "waiting"
    publisher.assert_called_once()


def test_publication_failure_propagates():
    verifier = Mock(
        side_effect=NamespaceBootstrapNotReady(
            "Namespace unavailable."
        )
    )
    publisher = Mock(
        side_effect=RuntimeError("GitOps push failed.")
    )

    with pytest.raises(
        RuntimeError,
        match="GitOps push failed",
    ):
        reconcile(verifier, publisher)


def test_unexpected_verification_error_does_not_publish():
    verifier = Mock(
        side_effect=ValueError("Invalid bootstrap configuration.")
    )
    publisher = Mock()

    with pytest.raises(
        ValueError,
        match="Invalid bootstrap configuration",
    ):
        reconcile(verifier, publisher)

    publisher.assert_not_called()


def test_missing_kubernetes_client_fails_closed():
    verifier = Mock()
    publisher = Mock()

    with pytest.raises(
        NamespaceBootstrapNotReady,
        match="CoreV1Api",
    ):
        reconcile_namespace_bootstrap(
            repository_url="test-gitops-repository",
            spec=make_spec(),
            core_api=None,
            verifier=verifier,
            publisher=publisher,
        )

    verifier.assert_not_called()
    publisher.assert_not_called()


def test_empty_commit_sha_is_rejected():
    verifier = Mock(
        side_effect=NamespaceBootstrapNotReady(
            "Namespace unavailable."
        )
    )
    publisher = Mock(return_value=None)

    with pytest.raises(
        RuntimeError,
        match="no commit SHA",
    ):
        reconcile(verifier, publisher)


def test_repeated_reconciliation_checks_readiness_again():
    verifier = Mock(
        side_effect=[
            NamespaceBootstrapNotReady("Not ready."),
            f"ap-dev-{PROJECT_ID}",
        ]
    )
    publisher = Mock(return_value="bootstrap-commit-sha")

    first = reconcile(verifier, publisher)
    second = reconcile(verifier, publisher)

    assert first.status == "waiting"
    assert second.status == "ready"
    assert publisher.call_count == 1
