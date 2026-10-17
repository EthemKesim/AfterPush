from pathlib import Path

import yaml


WORKERS = Path(__file__).resolve().parents[2] / "k8s/workers"


def _load(path: str) -> list[dict]:
    return list(yaml.safe_load_all((WORKERS / path).read_text()))


def _cronjob(path: str) -> tuple[dict, dict]:
    cronjob = _load(path)[0]
    container = cronjob["spec"]["jobTemplate"]["spec"]["template"][
        "spec"
    ]["containers"][0]
    return cronjob, container


def test_publication_cronjob_is_explicitly_suspended_and_safe():
    cronjob, container = _cronjob("gitops-publication-cronjob.yaml")
    pod_spec = cronjob["spec"]["jobTemplate"]["spec"]["template"]["spec"]

    assert cronjob["spec"]["suspend"] is True
    assert cronjob["spec"]["concurrencyPolicy"] == "Forbid"
    assert pod_spec["serviceAccountName"] == "afterpush-publication-worker"
    assert container["args"] == ["--execute", "--limit", "20"]
    assert container["image"] == "REPLACE_WORKER_IMAGE"
    assert container["securityContext"]["allowPrivilegeEscalation"] is False
    assert container["securityContext"]["capabilities"]["drop"] == ["ALL"]


def test_recovery_cronjob_needs_no_kubernetes_api_token():
    cronjob, container = _cronjob("gitops-recovery-cronjob.yaml")
    pod_spec = cronjob["spec"]["jobTemplate"]["spec"]["template"]["spec"]

    assert cronjob["spec"]["suspend"] is True
    assert cronjob["spec"]["concurrencyPolicy"] == "Forbid"
    assert pod_spec["serviceAccountName"] == "afterpush-gitops-recovery"
    assert pod_spec["automountServiceAccountToken"] is False
    assert container["args"] == [
        "--timeout-minutes",
        "15",
        "--limit",
        "100",
    ]


def test_publication_rbac_is_read_only_for_prerequisite_checks():
    manifests = _load("gitops-worker-rbac.yaml")
    role = next(item for item in manifests if item["kind"] == "ClusterRole")

    assert role["rules"] == [
        {
            "apiGroups": [""],
            "resources": ["namespaces", "resourcequotas", "limitranges"],
            "verbs": ["get"],
        },
        {
            "apiGroups": ["rbac.authorization.k8s.io"],
            "resources": ["roles", "rolebindings"],
            "verbs": ["get"],
        },
    ]


def test_gitops_worker_credentials_are_references_not_embedded_values():
    cronjob, container = _cronjob("gitops-publication-cronjob.yaml")
    del cronjob
    environment = {entry["name"]: entry for entry in container["env"]}

    assert environment["AFTERPUSH_GITOPS_REPOSITORY_URL"]["valueFrom"]
    assert environment["AFTERPUSH_GITOPS_USERNAME"]["valueFrom"]
    assert environment["AFTERPUSH_GITOPS_TOKEN"]["valueFrom"]

    config, secret = _load("gitops-worker-config.example.yaml")
    assert config["kind"] == "ConfigMap"
    assert secret["kind"] == "Secret"
    assert secret["stringData"]["AFTERPUSH_GITOPS_TOKEN"] == "REPLACE_ME"
