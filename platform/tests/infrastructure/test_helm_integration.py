
import subprocess
import sys
import tempfile
from pathlib import Path
from uuid import UUID

import yaml

from afterpush_api.services.bootstrap import (
    bootstrap_gitops_application,
    build_resource_name,
)


PROJECT_ROOT = Path(__file__).resolve().parents[3]

GENERATOR_PATH = PROJECT_ROOT / "platform/generator/generate.py"
CONFIG_PATH = PROJECT_ROOT / "platform/examples/afterpush.yaml"
CHART_PATH = PROJECT_ROOT / "helm/afterpush"

PROJECT_A = UUID("123e4567-e89b-12d3-a456-426614174000")
PROJECT_B = UUID("123e4567-e89b-12d3-a456-426614174001")

TEST_NAMESPACE = (
    "ap-staging-123e4567-e89b-12d3-a456-426614174000"
)


def render_values_file(
    values_path: Path,
    namespace: str = "default",
) -> str:
    result = subprocess.run(
        [
            "helm",
            "template",
            "afterpush",
            str(CHART_PATH),
            "-f",
            str(values_path),
            "--namespace",
            namespace,
        ],
        check=True,
        capture_output=True,
        text=True,
    )

    return result.stdout


def parse_resources(rendered: str) -> list[dict]:
    return [
        document
        for document in yaml.safe_load_all(rendered)
        if isinstance(document, dict)
    ]


def render_chart(
    resource_name: str | None = None,
    namespace: str = "default",
) -> str:
    generated_values = subprocess.run(
        [
            sys.executable,
            str(GENERATOR_PATH),
            str(CONFIG_PATH),
        ],
        check=True,
        capture_output=True,
        text=True,
    ).stdout

    values = yaml.safe_load(generated_values)

    if resource_name is not None:
        values.setdefault("application", {})[
            "resourceName"
        ] = resource_name

    with tempfile.NamedTemporaryFile(
        mode="w",
        suffix=".yaml",
        delete=False,
    ) as file:
        yaml.safe_dump(values, file)
        values_path = Path(file.name)

    try:
        return render_values_file(
            values_path,
            namespace=namespace,
        )
    finally:
        values_path.unlink(missing_ok=True)


def render_resources(
    resource_name: str | None = None,
    namespace: str = "default",
) -> list[dict]:
    return parse_resources(
        render_chart(resource_name, namespace)
    )


def find_resource(
    resources: list[dict],
    kind: str,
) -> dict:
    matches = [
        resource
        for resource in resources
        if resource.get("kind") == kind
    ]

    assert len(matches) == 1, (
        f"Expected one {kind}, found {len(matches)}"
    )

    return matches[0]


def resource_identities(
    resources: list[dict],
) -> set[tuple[str, str, str]]:
    return {
        (
            resource.get("apiVersion", ""),
            resource["kind"],
            resource["metadata"]["name"],
        )
        for resource in resources
    }


def bootstrap_project_resources(
    gitops_root: Path,
    project_id: UUID,
    application_name: str = "backend-api",
) -> list[dict]:
    values_path = bootstrap_gitops_application(
        gitops_root=gitops_root,
        application_name=application_name,
        environment="staging",
        image_repository="nginx",
        image_tag="v1.0.0",
        port=3000,
        replicas=2,
        project_id=project_id,
    )

    return parse_resources(
        render_values_file(values_path)
    )


def test_helm_chart_uses_application_identity():
    rendered = render_chart()

    assert "name: afterpush-api" in rendered
    assert "app: afterpush-api" in rendered


def test_deployment_uses_application_port():
    rendered = render_chart()

    assert "containerPort: 8000" in rendered


def test_helm_chart_preserves_afterpush_application_identity():
    resources = render_resources()

    deployment = find_resource(resources, "Deployment")
    service = find_resource(resources, "Service")
    service_monitor = find_resource(
        resources,
        "ServiceMonitor",
    )

    assert deployment["metadata"]["name"] == "afterpush-api"
    assert service["metadata"]["name"] == "afterpush-api"
    assert service_monitor["metadata"]["name"] == (
        "afterpush-api"
    )

    assert service_monitor["spec"]["selector"][
        "matchLabels"
    ] == {"app": "afterpush-api"}


def test_service_monitor_labels_application_scrapes():
    resources = render_resources(
        resource_name="payment-api-project-a",
        namespace=TEST_NAMESPACE,
    )

    service_monitor = find_resource(
        resources,
        "ServiceMonitor",
    )

    assert service_monitor["metadata"]["name"] == (
        "payment-api-project-a"
    )

    assert service_monitor["spec"]["selector"][
        "matchLabels"
    ] == {"app": "payment-api-project-a"}

    endpoint = service_monitor["spec"]["endpoints"][0]

    assert endpoint["port"] == "http"
    assert endpoint["path"] == "/metrics"

    relabelings = {
        item["targetLabel"]: item["replacement"]
        for item in endpoint["relabelings"]
    }

    assert relabelings["application"] == (
        "payment-api-project-a"
    )

    assert relabelings["scrape_type"] == "application"


def test_target_down_alert_is_project_aware():
    resources = render_resources(
        resource_name="payment-api-project-a",
        namespace=TEST_NAMESPACE,
    )

    prometheus_rule = find_resource(
        resources,
        "PrometheusRule",
    )

    rules = [
        rule
        for group in prometheus_rule["spec"]["groups"]
        for rule in group["rules"]
    ]

    target_down = next(
        rule
        for rule in rules
        if rule.get("alert") == "AfterPushTargetDown"
    )

    expression = target_down["expr"]

    assert f'namespace="{TEST_NAMESPACE}"' in expression
    assert 'application="payment-api-project-a"' in expression
    assert 'scrape_type="application"' in expression
    assert "up{" in expression
    assert "absent(" in expression

    assert 'job="payment-api-project-a"' not in expression


def test_blackbox_probe_uses_project_service_dns():
    resources = render_resources(
        resource_name="payment-api-project-a",
        namespace=TEST_NAMESPACE,
    )

    probe = find_resource(resources, "Probe")

    assert probe["metadata"]["name"] == (
        "payment-api-project-a-http"
    )

    assert probe["spec"]["jobName"] == (
        "payment-api-project-a-blackbox"
    )

    targets = probe["spec"]["targets"][
        "staticConfig"
    ]["static"]

    expected_target = (
        "http://payment-api-project-a."
        f"{TEST_NAMESPACE}.svc.cluster.local:80/health"
    )

    assert targets == [expected_target]

    assert probe["spec"]["targets"][
        "staticConfig"
    ]["labels"]["application"] == (
        "payment-api-project-a"
    )


def test_helm_templates_do_not_hardcode_environment_namespace():
    templates_path = CHART_PATH / "templates"

    for template_path in templates_path.glob("*.yaml"):
        template = template_path.read_text(encoding="utf-8")

        assert "afterpush-dev" not in template, (
            f"{template_path.name} contains a hardcoded "
            "environment namespace."
        )


def test_different_projects_have_distinct_kubernetes_resources():
    project_a = render_resources(
        resource_name="afterpush-api-project-a"
    )

    project_b = render_resources(
        resource_name="afterpush-api-project-b"
    )

    collisions = (
        resource_identities(project_a)
        & resource_identities(project_b)
    )

    assert not collisions, (
        f"Kubernetes resource names collide: {collisions}"
    )


def test_project_resource_selectors_are_consistent():
    resources = render_resources(
        resource_name="afterpush-api-project-a"
    )

    deployment = find_resource(resources, "Deployment")
    service = find_resource(resources, "Service")

    pod_labels = deployment["spec"]["template"][
        "metadata"
    ]["labels"]

    deployment_selector = deployment["spec"][
        "selector"
    ]["matchLabels"]

    service_selector = service["spec"]["selector"]

    assert deployment_selector == service_selector

    for key, value in service_selector.items():
        assert pod_labels.get(key) == value

    assert deployment["metadata"]["name"] == (
        "afterpush-api-project-a"
    )

    assert service["metadata"]["name"] == (
        "afterpush-api-project-a"
    )


def test_bootstrap_values_render_unique_project_resources(tmp_path):
    resources_a = bootstrap_project_resources(
        tmp_path,
        PROJECT_A,
    )

    resources_b = bootstrap_project_resources(
        tmp_path,
        PROJECT_B,
    )

    expected_a = build_resource_name(
        "backend-api",
        PROJECT_A,
    )

    expected_b = build_resource_name(
        "backend-api",
        PROJECT_B,
    )

    for resources, expected_name in (
        (resources_a, expected_a),
        (resources_b, expected_b),
    ):
        deployment = find_resource(resources, "Deployment")
        service = find_resource(resources, "Service")
        configmap = find_resource(resources, "ConfigMap")

        assert deployment["metadata"]["name"] == expected_name
        assert service["metadata"]["name"] == expected_name
        assert configmap["metadata"]["name"] == (
            f"{expected_name}-config"
        )

        assert deployment["spec"]["selector"]["matchLabels"] == (
            service["spec"]["selector"]
        )

    collisions = (
        resource_identities(resources_a)
        & resource_identities(resources_b)
    )

    assert not collisions, (
        f"Project resources collide: {collisions}"
    )


def test_bootstrap_values_isolate_apps_within_same_project(tmp_path):
    backend_api = bootstrap_project_resources(
        tmp_path,
        PROJECT_A,
        application_name="backend-api",
    )

    backend_worker = bootstrap_project_resources(
        tmp_path,
        PROJECT_A,
        application_name="backend-worker",
    )

    api_deployment = find_resource(
        backend_api,
        "Deployment",
    )

    worker_deployment = find_resource(
        backend_worker,
        "Deployment",
    )

    assert api_deployment["metadata"]["name"] != (
        worker_deployment["metadata"]["name"]
    )

    collisions = (
        resource_identities(backend_api)
        & resource_identities(backend_worker)
    )

    assert not collisions, (
        f"Applications in the same project collide: {collisions}"
    )
