from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[3]
ARGOCD = ROOT / "argocd" / "applications"


def load(name):
    return yaml.safe_load((ARGOCD / name).read_text(encoding="utf-8"))


def test_bootstrap_project_permissions():
    project = load("afterpush-namespace-bootstrap-project.yaml")
    spec = project["spec"]

    assert project["kind"] == "AppProject"
    assert spec["clusterResourceWhitelist"] == [
        {"group": "", "kind": "Namespace"}
    ]
    assert spec["namespaceResourceWhitelist"] == [
        {"group": "", "kind": "ResourceQuota"},
        {"group": "", "kind": "LimitRange"},
    ]


def test_bootstrap_applicationset_identity():
    appset = load("afterpush-namespace-bootstrap-applicationset.yaml")
    spec = appset["spec"]

    assert spec["generators"][0]["git"]["directories"] == [
        {"path": "gitops/platform/namespaces/*/*"}
    ]

    template = spec["template"]["spec"]
    assert template["project"] == "afterpush-namespace-bootstrap"
    assert template["source"]["directory"]["include"] == "namespace.yaml"


def test_bootstrap_does_not_prune_namespaces():
    appset = load("afterpush-namespace-bootstrap-applicationset.yaml")
    automated = appset["spec"]["template"]["spec"]["syncPolicy"]["automated"]

    assert automated["prune"] is False


def test_workloads_cannot_create_namespaces():
    appset = load("afterpush-project-applicationset.yaml")
    template = appset["spec"]["template"]["spec"]

    options = template["syncPolicy"].get("syncOptions", [])

    assert "CreateNamespace=true" not in options


def test_workload_project_has_no_namespace_permission():
    project = load("afterpush-workloads-project.yaml")
    spec = project["spec"]

    assert spec.get("clusterResourceWhitelist", []) == []


def test_rbac_applicationsets_use_separate_manifests():
    argocd = load("afterpush-platform-argocd-rbac-applicationset.yaml")
    deployment = load("afterpush-platform-deployment-rbac-applicationset.yaml")

    argocd_spec = argocd["spec"]["template"]["spec"]
    deployment_spec = deployment["spec"]["template"]["spec"]

    assert argocd_spec["source"]["directory"]["include"] == "argocd-rbac.yaml"
    assert deployment_spec["source"]["directory"]["include"] == "deployment-rbac.yaml"
    assert argocd_spec["destination"]["namespace"] == "argocd"
    assert deployment_spec["destination"]["namespace"] == (
        "ap-{{ index .path.segments 4 }}-{{ index .path.segments 5 }}"
    )
