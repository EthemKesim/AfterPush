from pathlib import Path

import yaml


MANIFEST = (
    Path(__file__).resolve().parents[2]
    / "k8s/workers/namespace-bootstrap-job.yaml"
)


def load_job():
    documents = list(yaml.safe_load_all(MANIFEST.read_text()))
    assert len(documents) == 1
    return documents[0]


def test_job_identity():
    job = load_job()

    assert job["apiVersion"] == "batch/v1"
    assert job["kind"] == "Job"
    assert job["metadata"]["namespace"] == "afterpush-system"

    pod_spec = job["spec"]["template"]["spec"]

    assert pod_spec["serviceAccountName"] == (
        "afterpush-namespace-bootstrap"
    )


def test_job_is_dry_run_only():
    pod_spec = load_job()["spec"]["template"]["spec"]
    container = pod_spec["containers"][0]

    assert container["command"] == [
        "python",
        "-m",
        "afterpush_api.workers.namespace_bootstrap",
    ]

    assert "--execute" not in container.get("args", [])

    assert "AFTERPUSH_GITOPS_REPOSITORY_URL" not in {
        item["name"] for item in container.get("env", [])
    }

    assert pod_spec["automountServiceAccountToken"] is False


def test_job_has_restricted_security_context():
    pod_spec = load_job()["spec"]["template"]["spec"]
    container = pod_spec["containers"][0]

    assert pod_spec["securityContext"]["runAsNonRoot"] is True
    assert pod_spec["securityContext"]["runAsUser"] == 10001
    assert pod_spec["securityContext"]["seccompProfile"]["type"] == (
        "RuntimeDefault"
    )

    security = container["securityContext"]

    assert security["allowPrivilegeEscalation"] is False
    assert security["capabilities"]["drop"] == ["ALL"]


def test_job_uses_database_secret():
    container = load_job()["spec"]["template"]["spec"]["containers"][0]

    database_env = next(
        item
        for item in container["env"]
        if item["name"] == "DATABASE_URL"
    )

    assert database_env["valueFrom"]["secretKeyRef"] == {
        "name": "afterpush-api-db",
        "key": "DATABASE_URL",
    }


def test_job_has_resource_limits():
    container = load_job()["spec"]["template"]["spec"]["containers"][0]

    resources = container["resources"]

    assert resources["requests"]["cpu"] == "100m"
    assert resources["requests"]["memory"] == "128Mi"
    assert resources["limits"]["cpu"] == "500m"
    assert resources["limits"]["memory"] == "512Mi"
