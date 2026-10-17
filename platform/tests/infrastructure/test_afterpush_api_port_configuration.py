import subprocess
from pathlib import Path

import pytest
import yaml


PROJECT_ROOT = Path(__file__).resolve().parents[3]
CHART_PATH = PROJECT_ROOT / "helm/afterpush"
VALUE_FILES = (
    PROJECT_ROOT / "gitops/apps/afterpush-api/values.yaml",
    PROJECT_ROOT / "gitops/apps/afterpush-api/values-local.yaml",
    PROJECT_ROOT / "gitops/apps/afterpush-api/values-eks.yaml",
)


def _render(values_path: Path) -> list[dict]:
    result = subprocess.run(
        [
            "helm",
            "template",
            "afterpush-api",
            str(CHART_PATH),
            "-f",
            str(values_path),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    return [
        resource
        for resource in yaml.safe_load_all(result.stdout)
        if isinstance(resource, dict)
    ]


@pytest.mark.parametrize("values_path", VALUE_FILES)
def test_afterpush_api_helm_values_match_uvicorn_port(values_path):
    values = yaml.safe_load(values_path.read_text())
    resources = _render(values_path)

    deployment = next(
        resource for resource in resources if resource["kind"] == "Deployment"
    )
    service = next(
        resource for resource in resources if resource["kind"] == "Service"
    )
    container = deployment["spec"]["template"]["spec"]["containers"][0]

    assert values["service"]["targetPort"] == 8000
    assert container["ports"][0]["containerPort"] == 8000
    assert container["readinessProbe"]["httpGet"]["port"] == 8000
    assert container["livenessProbe"]["httpGet"]["port"] == 8000
    assert service["spec"]["ports"][0]["targetPort"] == 8000


def test_local_static_manifest_matches_uvicorn_port():
    deployment = yaml.safe_load(
        (PROJECT_ROOT / "k8s/deployment.yaml").read_text()
    )
    service = yaml.safe_load(
        (PROJECT_ROOT / "k8s/service.yaml").read_text()
    )
    container = deployment["spec"]["template"]["spec"]["containers"][0]

    assert '"--port", "8000"' in (
        PROJECT_ROOT / "platform/Dockerfile.api"
    ).read_text()
    assert container["ports"][0]["containerPort"] == 8000
    assert container["readinessProbe"]["httpGet"]["port"] == 8000
    assert container["livenessProbe"]["httpGet"]["port"] == 8000
    assert service["spec"]["ports"][0]["targetPort"] == 8000
