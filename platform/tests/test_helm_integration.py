import subprocess
import sys
import tempfile
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]

GENERATOR_PATH = (
    PROJECT_ROOT / "platform/generator/generate.py"
)

CONFIG_PATH = (
    PROJECT_ROOT / "platform/examples/afterpush.yaml"
)

CHART_PATH = (
    PROJECT_ROOT / "helm/afterpush"
)


def render_chart() -> str:
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

    with tempfile.NamedTemporaryFile(
        mode="w",
        suffix=".yaml",
        delete=False,
    ) as file:
        file.write(generated_values)
        values_path = file.name

    try:
        result = subprocess.run(
            [
                "helm",
                "template",
                "afterpush",
                str(CHART_PATH),
                "-f",
                values_path,
            ],
            check=True,
            capture_output=True,
            text=True,
        )

        return result.stdout

    finally:
        Path(values_path).unlink(missing_ok=True)


def test_helm_chart_uses_application_identity():
    rendered = render_chart()

    assert "name: demo-api" in rendered
    assert "app: demo-api" in rendered


def test_deployment_uses_application_port():
    rendered = render_chart()

    assert "containerPort: 3000" in rendered


def test_helm_chart_does_not_use_old_application_identity():
    rendered = render_chart()

    # The Docker image repository may legitimately still be
    # named afterpush-api. We only reject the old Kubernetes
    # resource identity patterns.
    assert "name: afterpush-api\n" not in rendered
    assert "app: afterpush-api" not in rendered
    assert 'job="afterpush-api"' not in rendered

def test_helm_templates_do_not_hardcode_environment_namespace():
    templates_path = CHART_PATH / "templates"

    for template_path in templates_path.glob("*.yaml"):
        template = template_path.read_text(encoding="utf-8")

        assert "afterpush-dev" not in template, (
            f"{template_path.name} contains a hardcoded environment namespace."
        )