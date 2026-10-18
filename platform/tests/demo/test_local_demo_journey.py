import sys
from pathlib import Path

import yaml


PROJECT_ROOT = Path(__file__).resolve().parents[3]
PLATFORM_ROOT = PROJECT_ROOT / "platform"

if str(PLATFORM_ROOT) not in sys.path:
    sys.path.insert(0, str(PLATFORM_ROOT))

from afterpush_cli.main import deploy_command, render_command, validate_command  # noqa: E402
from afterpush_api.models import Deployment  # noqa: E402


EXAMPLE_PATH = PLATFORM_ROOT / "examples" / "afterpush.yaml"


def test_local_demo_journey_validates_renders_and_promotes(client, db_session, tmp_path, capsys):
    """Exercise the documented local demo without GitHub or Kubernetes access."""
    assert validate_command(EXAMPLE_PATH) == 0
    assert "AfterPush configuration is valid" in capsys.readouterr().out

    assert render_command(EXAMPLE_PATH) == 0
    rendered_values = yaml.safe_load(capsys.readouterr().out)
    assert rendered_values["application"]["name"] == "afterpush-api"
    assert rendered_values["service"]["targetPort"] == 8000

    project = client.post(
        "/api/v1/projects",
        json={
            "name": "local-demo-project",
            "repository_url": "https://github.com/example/local-demo",
        },
    )
    assert project.status_code == 201

    application = client.post(
        f"/api/v1/projects/{project.json()['id']}/applications",
        json={
            "name": "afterpush-api",
            "image": "afterpush-api",
            "port": 8000,
            "replicas": 2,
        },
    )
    assert application.status_code == 201

    deployment = client.post(
        f"/api/v1/applications/{application.json()['id']}/deployments",
        json={"environment": "dev", "image_tag": "metrics"},
    )
    assert deployment.status_code == 201
    assert deployment.json()["status"] == "pending"

    gitops_root = tmp_path / "gitops" / "apps"
    assert deploy_command(EXAMPLE_PATH, gitops_root=gitops_root) == 0
    values_path = gitops_root / "afterpush-api" / "values.yaml"
    generated_values = yaml.safe_load(values_path.read_text(encoding="utf-8"))
    assert generated_values["image"] == {
        "repository": "afterpush-api",
        "tag": "metrics",
        "pullPolicy": "Never",
    }

    dev_deployment = db_session.get(Deployment, deployment.json()["id"])
    assert dev_deployment is not None
    dev_deployment.status = "published"
    dev_deployment.runtime_status = "healthy"
    dev_deployment.published_commit_sha = "a" * 40
    db_session.commit()

    promotion = client.post(
        f"/api/v1/deployments/{deployment.json()['id']}/promote",
        json={"target_environment": "staging"},
    )
    assert promotion.status_code == 201
    assert promotion.json()["environment"] == "staging"
    assert promotion.json()["promotion_source_deployment_id"] == deployment.json()["id"]
