from pathlib import Path

import yaml


PROJECT_ROOT = Path(__file__).resolve().parents[3]


def _load(path: str) -> list[dict]:
    return list(
        yaml.safe_load_all((PROJECT_ROOT / path).read_text())
    )


def _runtime_container(manifest: dict) -> dict:
    return manifest["spec"]["jobTemplate"]["spec"]["template"][
        "spec"
    ]["containers"][0]


def test_runtime_cronjob_is_safe_to_apply_before_activation():
    cronjob = _load("k8s/runtime-reconciliation/cronjob.yaml")[0]
    pod_spec = cronjob["spec"]["jobTemplate"]["spec"]["template"][
        "spec"
    ]
    container = _runtime_container(cronjob)

    assert cronjob["spec"]["suspend"] is True
    assert cronjob["spec"]["concurrencyPolicy"] == "Forbid"
    assert cronjob["spec"]["jobTemplate"]["spec"][
        "ttlSecondsAfterFinished"
    ] == 3600
    assert pod_spec["serviceAccountName"] == "afterpush-runtime-worker"
    assert pod_spec["automountServiceAccountToken"] is True
    assert pod_spec["securityContext"]["runAsNonRoot"] is True
    assert container["image"] == "REPLACE_RUNTIME_WORKER_IMAGE"
    assert container["securityContext"]["readOnlyRootFilesystem"] is True
    assert container["securityContext"]["allowPrivilegeEscalation"] is False
    assert container["securityContext"]["capabilities"]["drop"] == ["ALL"]
    assert container["env"][0]["valueFrom"]["secretKeyRef"]["name"] == (
        "afterpush-api-db"
    )
    assert container["env"][1]["valueFrom"]["configMapKeyRef"] == {
        "name": "afterpush-runtime-worker-config",
        "key": "AFTERPUSH_GITOPS_REPOSITORY_URL",
    }


def test_runtime_config_contains_no_credentials():
    config = _load("k8s/runtime-reconciliation/config.example.yaml")[0]

    assert config["kind"] == "ConfigMap"
    assert config["metadata"]["name"] == "afterpush-runtime-worker-config"
    assert set(config["data"]) == {"AFTERPUSH_GITOPS_REPOSITORY_URL"}


def test_one_off_runtime_job_uses_the_same_hardened_contract():
    job = _load("platform/k8s/workers/runtime-job.yaml")[0]
    pod_spec = job["spec"]["template"]["spec"]
    container = pod_spec["containers"][0]

    assert pod_spec["automountServiceAccountToken"] is True
    assert pod_spec["securityContext"]["runAsNonRoot"] is True
    assert container["securityContext"]["readOnlyRootFilesystem"] is True
    assert container["env"][1]["valueFrom"]["configMapKeyRef"][
        "name"
    ] == "afterpush-runtime-worker-config"
