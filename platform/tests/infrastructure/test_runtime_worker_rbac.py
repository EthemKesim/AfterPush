from pathlib import Path

import yaml


ROOT_MANIFEST = (
    Path(__file__).resolve().parents[3]
    / "k8s/runtime-reconciliation/rbac.yaml"
)
WORKER_MANIFEST = (
    Path(__file__).resolve().parents[2]
    / "k8s/workers/runtime-rbac.yaml"
)


def _load(path: Path) -> list[dict]:
    return list(yaml.safe_load_all(path.read_text()))


def test_runtime_worker_bootstrap_grants_no_cluster_wide_access():
    manifests = _load(ROOT_MANIFEST)

    assert [item["kind"] for item in manifests] == [
        "Namespace",
        "ServiceAccount",
    ]
    assert all(
        item["kind"] not in {"ClusterRole", "ClusterRoleBinding"}
        for item in manifests
    )
    assert manifests[1]["automountServiceAccountToken"] is True


def test_runtime_worker_rbac_is_generated_per_deployment():
    manifests = _load(WORKER_MANIFEST)

    assert [item["kind"] for item in manifests] == ["ServiceAccount"]
    assert manifests[0]["metadata"] == {
        "name": "afterpush-runtime-worker",
        "namespace": "afterpush-system",
    }
    assert manifests[0]["automountServiceAccountToken"] is True
