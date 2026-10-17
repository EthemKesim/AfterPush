from uuid import UUID

import pytest
import yaml

from afterpush_api.services.argocd_identity import (
    build_argocd_application_identity,
)
from afterpush_api.services.argocd_observer_rbac import (
    render_argocd_application_rbac,
)


PROJECT_ID = UUID("12345678-1234-5678-1234-567812345678")


def render_manifests(
    *,
    application_name="afterpush-api",
    environment="dev",
):
    rendered = render_argocd_application_rbac(
        project_id=PROJECT_ID,
        application_name=application_name,
        environment=environment,
    )
    return list(yaml.safe_load_all(rendered))


@pytest.mark.parametrize("environment", ["dev", "staging", "prod"])
def test_role_targets_exact_argocd_application(environment):
    identity = build_argocd_application_identity(
        project_id=PROJECT_ID,
        application_name="afterpush-api",
        environment=environment,
    )

    manifests = render_manifests(environment=environment)

    assert len(manifests) == 2

    role = manifests[0]

    assert role["kind"] == "Role"
    assert role["metadata"]["namespace"] == "argocd"

    assert role["rules"] == [
        {
            "apiGroups": ["argoproj.io"],
            "resources": ["applications"],
            "resourceNames": [identity.application_name],
            "verbs": ["get"],
        }
    ]


def test_binding_targets_correct_service_account():
    manifests = render_manifests()

    role, binding = manifests

    assert binding["kind"] == "RoleBinding"
    assert binding["metadata"]["namespace"] == "argocd"

    assert binding["subjects"] == [
        {
            "kind": "ServiceAccount",
            "name": "afterpush-runtime-worker",
            "namespace": "afterpush-system",
        }
    ]

    assert binding["roleRef"] == {
        "kind": "Role",
        "name": role["metadata"]["name"],
        "apiGroup": "rbac.authorization.k8s.io",
    }


def test_renderer_is_deterministic():
    first = render_argocd_application_rbac(
        project_id=PROJECT_ID,
        application_name="afterpush-api",
        environment="dev",
    )

    second = render_argocd_application_rbac(
        project_id=PROJECT_ID,
        application_name="afterpush-api",
        environment="dev",
    )

    assert first == second


def test_different_projects_get_different_roles():
    first = render_argocd_application_rbac(
        project_id=PROJECT_ID,
        application_name="afterpush-api",
        environment="dev",
    )

    second = render_argocd_application_rbac(
        project_id=UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"),
        application_name="afterpush-api",
        environment="dev",
    )

    first_role = list(yaml.safe_load_all(first))[0]
    second_role = list(yaml.safe_load_all(second))[0]

    assert (
        first_role["metadata"]["name"]
        != second_role["metadata"]["name"]
    )

    assert (
        first_role["rules"][0]["resourceNames"]
        != second_role["rules"][0]["resourceNames"]
    )


def test_no_cluster_wide_permissions():
    manifests = render_manifests()

    assert [item["kind"] for item in manifests] == [
        "Role",
        "RoleBinding",
    ]

    assert all(
        item["kind"] not in {"ClusterRole", "ClusterRoleBinding"}
        for item in manifests
    )


def test_invalid_environment_is_rejected():
    with pytest.raises(ValueError):
        render_argocd_application_rbac(
            project_id=PROJECT_ID,
            application_name="afterpush-api",
            environment="../invalid",
        )
