from types import SimpleNamespace
from unittest.mock import Mock, patch
from uuid import uuid4

import pytest

from afterpush_api.services.deployment_prerequisites_dry_run import (
    inspect_pending_prerequisites,
)
from afterpush_api.services.namespace_bootstrap_readiness import (
    NamespaceBootstrapNotReady,
)
from afterpush_api.services.gitops_rbac_readiness import (
    GitOpsRBACNotReady,
)


MODULE = "afterpush_api.services.deployment_prerequisites_dry_run"


def make_context():
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
        name="orders-api",
    )

    db = Mock()

    def get_model(model, identifier):
        if model.__name__ == "Deployment":
            return deployment if identifier == deployment_id else None

        if model.__name__ == "Application":
            return application if identifier == application_id else None

        return None

    db.get.side_effect = get_model

    return db, deployment_id, project_id


def run_inspection(
    *,
    namespace_error=None,
    rbac_error=None,
):
    db, deployment_id, project_id = make_context()

    namespace = Mock(side_effect=namespace_error)
    rbac = Mock(side_effect=rbac_error)

    core_api = object()
    rbac_api = object()

    with (
        patch(
            f"{MODULE}.get_pending_deployment_ids",
            return_value=[deployment_id],
        ) as selector,
        patch(
            f"{MODULE}.verify_namespace_bootstrap",
            namespace,
        ),
        patch(
            f"{MODULE}.verify_gitops_rbac",
            rbac,
        ),
    ):
        result = inspect_pending_prerequisites(
            db=db,
            core_api=core_api,
            rbac_api=rbac_api,
            limit=1,
        )

    selector.assert_called_once_with(db, limit=1)
    db.rollback.assert_called_once()

    return result, namespace, rbac, project_id, core_api, rbac_api


def test_ready_namespace_and_rbac():
    result, namespace, rbac, project_id, core_api, rbac_api = (
        run_inspection()
    )

    assert result == {
        "ready": 1,
        "namespace_not_ready": 0,
        "rbac_not_ready": 0,
        "skipped": 0,
        "errors": 0,
    }

    namespace.assert_called_once_with(
        core_api=core_api,
        project_id=project_id,
        application_name="orders-api",
        environment="dev",
    )

    rbac.assert_called_once_with(
        rbac_api=rbac_api,
        project_id=project_id,
        application_name="orders-api",
        environment="dev",
    )


def test_missing_namespace_skips_rbac_check():
    result, namespace, rbac, *_ = run_inspection(
        namespace_error=NamespaceBootstrapNotReady(
            "Namespace missing"
        )
    )

    assert result["namespace_not_ready"] == 1
    assert result["ready"] == 0
    assert result["errors"] == 0

    namespace.assert_called_once()
    rbac.assert_not_called()


def test_missing_rbac_after_ready_namespace():
    result, namespace, rbac, *_ = run_inspection(
        rbac_error=GitOpsRBACNotReady(
            "RoleBinding missing"
        )
    )

    assert result["rbac_not_ready"] == 1
    assert result["ready"] == 0
    assert result["errors"] == 0

    namespace.assert_called_once()
    rbac.assert_called_once()


def test_unexpected_kubernetes_error_is_not_ready():
    result, namespace, rbac, *_ = run_inspection(
        namespace_error=RuntimeError("Kubernetes API unavailable")
    )

    assert result["errors"] == 1
    assert result["ready"] == 0
    assert result["namespace_not_ready"] == 0

    namespace.assert_called_once()
    rbac.assert_not_called()


def test_missing_kubernetes_clients_are_rejected():
    db, _, _ = make_context()

    with pytest.raises(ValueError, match="Both Kubernetes clients"):
        inspect_pending_prerequisites(
            db=db,
            core_api=None,
            rbac_api=None,
        )

    db.get.assert_not_called()


def test_invalid_limit_is_rejected():
    db, _, _ = make_context()

    with pytest.raises(ValueError, match="limit"):
        inspect_pending_prerequisites(
            db=db,
            core_api=object(),
            rbac_api=object(),
            limit=0,
        )

    db.get.assert_not_called()
