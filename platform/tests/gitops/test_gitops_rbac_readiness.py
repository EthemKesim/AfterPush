from types import SimpleNamespace
from unittest.mock import MagicMock
from uuid import uuid4

import pytest
import yaml

from afterpush_api.services.argocd_observer_rbac import (
    render_argocd_application_rbac,
)
from afterpush_api.services.kubernetes_observer_rbac import (
    render_project_deployment_rbac,
)
from afterpush_api.services.gitops_rbac_readiness import (
    GitOpsRBACNotReady,
    verify_gitops_rbac,
)


PROJECT_ID = uuid4()
APPLICATION_NAME = "payment-api"
ENVIRONMENT = "dev"


def _object(value):
    if isinstance(value, dict):
        return SimpleNamespace(
            **{
                {
                    "apiGroups": "api_groups",
                    "resourceNames": "resource_names",
                    "roleRef": "role_ref",
                    "apiGroup": "api_group",
                }.get(key, key): _object(item)
                for key, item in value.items()
            }
        )
    if isinstance(value, list):
        return [_object(item) for item in value]
    return value


def _api():
    api = MagicMock()

    documents = []

    for rendered in (
        render_argocd_application_rbac(
            project_id=PROJECT_ID,
            application_name=APPLICATION_NAME,
            environment=ENVIRONMENT,
        ),
        render_project_deployment_rbac(
            project_id=PROJECT_ID,
            application_name=APPLICATION_NAME,
            environment=ENVIRONMENT,
        ),
    ):
        documents.extend(yaml.safe_load_all(rendered))

    roles = {
        (doc["metadata"]["name"], doc["metadata"]["namespace"]): _object(doc)
        for doc in documents
        if doc["kind"] == "Role"
    }

    bindings = {
        (doc["metadata"]["name"], doc["metadata"]["namespace"]): _object(doc)
        for doc in documents
        if doc["kind"] == "RoleBinding"
    }

    api.read_namespaced_role.side_effect = (
        lambda name, namespace: roles[(name, namespace)]
    )
    api.read_namespaced_role_binding.side_effect = (
        lambda name, namespace: bindings[(name, namespace)]
    )

    return api, roles, bindings


def _verify(api):
    return verify_gitops_rbac(
        rbac_api=api,
        project_id=PROJECT_ID,
        application_name=APPLICATION_NAME,
        environment=ENVIRONMENT,
    )


def test_correct_rbac_is_ready():
    api, _, _ = _api()
    _verify(api)
    assert api.read_namespaced_role.call_count == 2
    assert api.read_namespaced_role_binding.call_count == 2


def test_missing_rbac_api_fails_closed():
    with pytest.raises(GitOpsRBACNotReady):
        _verify(None)


def test_missing_role_fails_closed():
    api, _, _ = _api()
    api.read_namespaced_role.side_effect = RuntimeError("NotFound")

    with pytest.raises(GitOpsRBACNotReady):
        _verify(api)


def test_excessive_role_permissions_are_rejected():
    api, roles, _ = _api()
    first_role = next(iter(roles.values()))
    first_role.rules[0].verbs.append("list")

    with pytest.raises(GitOpsRBACNotReady, match="Role policy mismatch"):
        _verify(api)


def test_wrong_service_account_is_rejected():
    api, _, bindings = _api()
    first_binding = next(iter(bindings.values()))
    first_binding.subjects[0].name = "unexpected-worker"

    with pytest.raises(GitOpsRBACNotReady, match="RoleBinding policy mismatch"):
        _verify(api)


def test_wrong_resource_name_is_rejected():
    api, roles, _ = _api()
    first_role = next(iter(roles.values()))
    first_role.rules[0].resource_names = ["another-application"]

    with pytest.raises(GitOpsRBACNotReady, match="Role policy mismatch"):
        _verify(api)
