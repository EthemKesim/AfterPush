from pathlib import Path

import pytest
import yaml


ROOT = Path(__file__).resolve().parents[3]
RBAC_DIR = ROOT / "k8s" / "observer"

SERVICE_ACCOUNT = "afterpush-runtime-worker"
SERVICE_ACCOUNT_NAMESPACE = "afterpush-system"
PROJECT_NAMESPACE = "PROJECT_NAMESPACE"


def load_manifests(filename: str) -> list[dict]:
    path = RBAC_DIR / filename
    return list(yaml.safe_load_all(path.read_text()))


def test_argocd_static_manifest_contains_only_service_account():
    manifests = load_manifests("argocd-reader-rbac.yaml")

    assert len(manifests) == 1
    assert manifests[0]["kind"] == "ServiceAccount"
    assert manifests[0]["apiVersion"] == "v1"


def test_service_account_identity():
    manifests = load_manifests("argocd-reader-rbac.yaml")
    service_account = manifests[0]

    assert service_account["metadata"] == {
        "name": SERVICE_ACCOUNT,
        "namespace": SERVICE_ACCOUNT_NAMESPACE,
    }


def test_static_argocd_manifest_grants_no_permissions():
    manifests = load_manifests("argocd-reader-rbac.yaml")

    assert all(
        item["kind"] not in {
            "Role",
            "RoleBinding",
            "ClusterRole",
            "ClusterRoleBinding",
        }
        for item in manifests
    )


def test_project_template_structure():
    manifests = load_manifests(
        "project-deployment-reader-rbac.yaml"
    )

    assert [item["kind"] for item in manifests] == [
        "Role",
        "RoleBinding",
    ]


def test_project_template_grants_only_deployment_get():
    manifests = load_manifests(
        "project-deployment-reader-rbac.yaml"
    )

    role = manifests[0]

    assert role["metadata"]["namespace"] == PROJECT_NAMESPACE
    assert role["rules"] == [
        {
            "apiGroups": ["apps"],
            "resources": ["deployments"],
            "verbs": ["get"],
        }
    ]


def test_project_template_binding_targets_observer():
    manifests = load_manifests(
        "project-deployment-reader-rbac.yaml"
    )

    binding = manifests[1]

    assert binding["metadata"]["namespace"] == PROJECT_NAMESPACE

    assert binding["subjects"] == [
        {
            "kind": "ServiceAccount",
            "name": SERVICE_ACCOUNT,
            "namespace": SERVICE_ACCOUNT_NAMESPACE,
        }
    ]

    assert binding["roleRef"] == {
        "kind": "Role",
        "name": "afterpush-deployment-reader",
        "apiGroup": "rbac.authorization.k8s.io",
    }


def test_project_template_is_not_cluster_wide():
    manifests = load_manifests(
        "project-deployment-reader-rbac.yaml"
    )

    assert all(
        item["kind"] not in {
            "ClusterRole",
            "ClusterRoleBinding",
        }
        for item in manifests
    )


def test_project_template_requires_namespace_rendering():
    manifests = load_manifests(
        "project-deployment-reader-rbac.yaml"
    )

    assert all(
        item["metadata"]["namespace"] == PROJECT_NAMESPACE
        for item in manifests
    )
