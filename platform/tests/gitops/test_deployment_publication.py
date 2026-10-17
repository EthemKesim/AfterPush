import subprocess
from pathlib import Path
from uuid import uuid4

import yaml

from afterpush_api.services.deployment_gitops import (
    DeploymentGitOpsSpec,
)
from afterpush_api.services.deployment_publication import (
    publish_deployment_gitops,
)


def git(*args) -> str:
    result = subprocess.run(
        ["git", *map(str, args)],
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout.strip()


def test_publishes_deployment_values_to_remote_main(tmp_path):
    remote = tmp_path / "remote.git"
    seed = tmp_path / "seed"
    verification = tmp_path / "verification"

    git("init", "--bare", "--initial-branch=main", remote)
    git("clone", remote, seed)

    git("-C", seed, "config", "user.name", "AfterPush Test")
    git(
        "-C", seed, "config",
        "user.email", "test@afterpush.local",
    )

    (seed / "README.md").write_text(
        "# AfterPush\n",
        encoding="utf-8",
    )

    git("-C", seed, "add", "README.md")
    git("-C", seed, "commit", "-m", "Initial commit")
    git("-C", seed, "push", "origin", "HEAD:main")

    project_id = uuid4()

    spec = DeploymentGitOpsSpec(
        application_name="payment-api",
        environment="staging",
        image_repository="example/payment-api",
        image_tag="v2.0.0",
        port=3000,
        replicas=2,
        project_id=project_id,
    )

    published_sha = publish_deployment_gitops(
        repository_url=str(remote),
        spec=spec,
    )

    assert published_sha is not None

    git("clone", "--branch", "main", remote, verification)

    values_path = (
        verification
        / "gitops"
        / "apps"
        / "staging"
        / str(project_id)
        / "payment-api"
        / "values.yaml"
    )

    assert values_path.is_file()

    values = yaml.safe_load(
        values_path.read_text(encoding="utf-8")
    )

    assert values["image"]["repository"] == "example/payment-api"
    assert values["image"]["tag"] == "v2.0.0"
    assert values["application"]["name"] == "payment-api"

    assert published_sha == git(
        "-C", verification, "rev-parse", "HEAD"
    )
