import subprocess
from pathlib import Path

import pytest
import yaml


PROJECT_ROOT = Path(__file__).resolve().parents[3]
CHART_PATH = PROJECT_ROOT / "helm/afterpush"
API_VALUE_FILES = (
    PROJECT_ROOT / "gitops/apps/afterpush-api/values.yaml",
    PROJECT_ROOT / "gitops/apps/afterpush-api/values-local.yaml",
    PROJECT_ROOT / "gitops/apps/afterpush-api/values-eks.yaml",
)


def _render(*arguments: str) -> list[dict]:
    result = subprocess.run(
        ["helm", "template", "afterpush", str(CHART_PATH), *arguments],
        check=True,
        capture_output=True,
        text=True,
    )
    return [
        resource
        for resource in yaml.safe_load_all(result.stdout)
        if isinstance(resource, dict)
    ]


def _deployment(resources: list[dict]) -> dict:
    return next(resource for resource in resources if resource["kind"] == "Deployment")


def test_workload_uses_dedicated_tokenless_service_account():
    resources = _render()
    deployment = _deployment(resources)
    service_account = next(
        resource for resource in resources if resource["kind"] == "ServiceAccount"
    )
    pod_spec = deployment["spec"]["template"]["spec"]

    assert service_account["metadata"]["name"] == "afterpush-api"
    assert service_account["automountServiceAccountToken"] is False
    assert pod_spec["serviceAccountName"] == "afterpush-api"
    assert pod_spec["automountServiceAccountToken"] is False
    assert pod_spec["securityContext"]["runAsNonRoot"] is True


@pytest.mark.parametrize("values_path", API_VALUE_FILES)
def test_afterpush_api_uses_read_only_root_filesystem(values_path):
    resources = _render("-f", str(values_path))
    container = _deployment(resources)["spec"]["template"]["spec"][
        "containers"
    ][0]

    assert container["securityContext"]["allowPrivilegeEscalation"] is False
    assert container["securityContext"]["readOnlyRootFilesystem"] is True
    assert container["securityContext"]["capabilities"]["drop"] == ["ALL"]


def test_existing_service_account_must_be_named():
    result = subprocess.run(
        [
            "helm",
            "template",
            "afterpush",
            str(CHART_PATH),
            "--set",
            "serviceAccount.create=false",
        ],
        capture_output=True,
        text=True,
    )

    assert result.returncode != 0
    assert "serviceAccount.name is required" in result.stderr
