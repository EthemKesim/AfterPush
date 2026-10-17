from uuid import UUID

import pytest
import yaml

from afterpush_api.services.argocd_identity import (
    build_argocd_application_identity,
)
from afterpush_api.services.kubernetes_observer_rbac import (
    render_project_deployment_rbac,
)
from afterpush_api.services.bootstrap import build_resource_name


PROJECT_ID = UUID("12345678-1234-5678-1234-567812345678")


@pytest.mark.parametrize("environment", ["dev", "staging", "prod"])
def test_renderer_uses_expected_project_namespace(environment):
    identity = build_argocd_application_identity(
        project_id=PROJECT_ID,
        application_name="afterpush-api",
        environment=environment,
    )

    rendered = render_project_deployment_rbac(
        project_id=PROJECT_ID,
        application_name="afterpush-api",
        environment=environment,
    )

    manifests = list(yaml.safe_load_all(rendered))

    assert len(manifests) == 2
    assert all(
        manifest["metadata"]["namespace"] == identity.namespace
        for manifest in manifests
    )


def test_renderer_grants_only_deployment_get_permission():
    rendered = render_project_deployment_rbac(
        project_id=PROJECT_ID,
        application_name="afterpush-api",
        environment="dev",
    )

    manifests = list(yaml.safe_load_all(rendered))
    role = next(item for item in manifests if item["kind"] == "Role")

    assert role["rules"] == [
        {
            "apiGroups": ["apps"],
            "resources": ["deployments"],
            "verbs": ["get"],
            "resourceNames": [
                build_resource_name("afterpush-api", PROJECT_ID)
            ],
        }
    ]


def test_renderer_binds_correct_service_account():
    rendered = render_project_deployment_rbac(
        project_id=PROJECT_ID,
        application_name="afterpush-api",
        environment="dev",
    )

    manifests = list(yaml.safe_load_all(rendered))
    binding = next(
        item for item in manifests if item["kind"] == "RoleBinding"
    )

    assert binding["subjects"] == [
        {
            "kind": "ServiceAccount",
            "name": "afterpush-runtime-worker",
            "namespace": "afterpush-system",
        }
    ]

    identity = build_argocd_application_identity(
        project_id=PROJECT_ID,
        application_name="afterpush-api",
        environment="dev",
    )

    assert binding["roleRef"] == {
        "kind": "Role",
        "name": f"{identity.application_name}-deployment-reader",
        "apiGroup": "rbac.authorization.k8s.io",
    }


def test_renderer_is_deterministic():
    arguments = {
        "project_id": PROJECT_ID,
        "application_name": "afterpush-api",
        "environment": "dev",
    }

    first = render_project_deployment_rbac(**arguments)
    second = render_project_deployment_rbac(**arguments)

    assert first == second


def test_renderer_does_not_leave_namespace_placeholder():
    rendered = render_project_deployment_rbac(
        project_id=PROJECT_ID,
        application_name="afterpush-api",
        environment="dev",
    )

    assert "PROJECT_NAMESPACE" not in rendered


def test_renderer_rejects_invalid_environment():
    with pytest.raises(ValueError):
        render_project_deployment_rbac(
            project_id=PROJECT_ID,
            application_name="afterpush-api",
            environment="../invalid",
        )


def test_two_applications_in_same_namespace_have_distinct_rbac():
    names = set()
    deployment_names = set()
    namespaces = set()

    for application_name in ("backend", "frontend"):
        rendered = render_project_deployment_rbac(
            project_id=PROJECT_ID,
            application_name=application_name,
            environment="dev",
        )

        manifests = list(yaml.safe_load_all(rendered))

        role = next(m for m in manifests if m["kind"] == "Role")
        binding = next(
            m for m in manifests if m["kind"] == "RoleBinding"
        )

        role_name = role["metadata"]["name"]
        binding_name = binding["metadata"]["name"]

        assert binding["roleRef"]["name"] == role_name
        assert binding_name == f"{role_name}-binding"

        assert len(role_name) <= 63
        assert len(binding_name) <= 63

        assert role["rules"][0]["verbs"] == ["get"]
        assert role["rules"][0]["resources"] == ["deployments"]
        assert role["rules"][0]["apiGroups"] == ["apps"]

        assert len(role["rules"][0]["resourceNames"]) == 1

        names.add(role_name)
        names.add(binding_name)

        deployment_names.update(
            role["rules"][0]["resourceNames"]
        )

        namespaces.add(role["metadata"]["namespace"])
        assert binding["metadata"]["namespace"] == (
            role["metadata"]["namespace"]
        )

    assert len(namespaces) == 1
    assert len(names) == 4
    assert len(deployment_names) == 2
