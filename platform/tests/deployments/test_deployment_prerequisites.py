from types import SimpleNamespace
from unittest.mock import Mock
from uuid import uuid4

import pytest

from afterpush_api.services.deployment_prerequisites import (
    reconcile_deployment_prerequisites,
)


def inputs():
    return {
        "repository_url": "https://example.com/gitops.git",
        "project_id": uuid4(),
        "application_name": "orders-api",
        "environment": "dev",
        "core_api": object(),
        "rbac_api": object(),
    }


def test_namespace_waiting_does_not_run_rbac():
    namespace = Mock(
        return_value=SimpleNamespace(
            status="waiting",
            commit_sha="namespace123",
        )
    )
    rbac = Mock()

    result = reconcile_deployment_prerequisites(
        **inputs(),
        namespace_reconciler=namespace,
        rbac_reconciler=rbac,
    )

    assert result.status == "waiting"
    assert result.stage == "namespace"
    assert result.commit_sha == "namespace123"
    namespace.assert_called_once()
    rbac.assert_not_called()


def test_rbac_waiting_after_namespace_ready():
    namespace = Mock(
        return_value=SimpleNamespace(
            status="ready",
            commit_sha=None,
        )
    )
    rbac = Mock(
        return_value=SimpleNamespace(
            status="waiting",
            commit_sha="rbac123",
        )
    )

    result = reconcile_deployment_prerequisites(
        **inputs(),
        namespace_reconciler=namespace,
        rbac_reconciler=rbac,
    )

    assert result.status == "waiting"
    assert result.stage == "rbac"
    assert result.commit_sha == "rbac123"
    namespace.assert_called_once()
    rbac.assert_called_once()


def test_both_ready():
    namespace = Mock(
        return_value=SimpleNamespace(
            status="ready",
            commit_sha=None,
        )
    )
    rbac = Mock(
        return_value=SimpleNamespace(
            status="ready",
            commit_sha=None,
        )
    )

    result = reconcile_deployment_prerequisites(
        **inputs(),
        namespace_reconciler=namespace,
        rbac_reconciler=rbac,
    )

    assert result.status == "ready"
    assert result.stage is None
    assert result.commit_sha is None


def test_invalid_namespace_status_fails_closed():
    namespace = Mock(
        return_value=SimpleNamespace(
            status="unknown",
            commit_sha=None,
        )
    )
    rbac = Mock()

    with pytest.raises(RuntimeError, match="namespace"):
        reconcile_deployment_prerequisites(
            **inputs(),
            namespace_reconciler=namespace,
            rbac_reconciler=rbac,
        )

    rbac.assert_not_called()


def test_invalid_rbac_status_fails_closed():
    namespace = Mock(
        return_value=SimpleNamespace(
            status="ready",
            commit_sha=None,
        )
    )
    rbac = Mock(
        return_value=SimpleNamespace(
            status="unknown",
            commit_sha=None,
        )
    )

    with pytest.raises(RuntimeError, match="RBAC"):
        reconcile_deployment_prerequisites(
            **inputs(),
            namespace_reconciler=namespace,
            rbac_reconciler=rbac,
        )
