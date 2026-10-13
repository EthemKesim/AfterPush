import subprocess
from uuid import uuid4

import pytest
import yaml

from afterpush_api.services.deployment_gitops import (
    ConflictingGitOpsRevisionError,
    DeploymentGitOpsSpec,
)
from afterpush_api.services.deployment_publication import (
    publish_deployment_gitops,
)


def git(*args, cwd=None):
    return subprocess.run(
        ["git", *args],
        cwd=cwd,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def test_same_revision_cannot_publish_different_image(tmp_path):
    remote = tmp_path / "remote.git"
    git("init", "--bare", "--initial-branch=main", str(remote))

    seed = tmp_path / "seed"
    git("clone", str(remote), str(seed))
    git("config", "user.name", "AfterPush Test", cwd=seed)
    git("config", "user.email", "test@afterpush.local", cwd=seed)

    (seed / "README.md").write_text("AfterPush test\n")
    git("add", "README.md", cwd=seed)
    git("commit", "-m", "Initial commit", cwd=seed)
    git("push", "origin", "HEAD:refs/heads/main", cwd=seed)

    project_id = uuid4()

    def spec(tag):
        return DeploymentGitOpsSpec(
            application_name="test-api",
            environment="dev",
            image_repository="example/test-api",
            image_tag=tag,
            port=3000,
            replicas=2,
            project_id=project_id,
            revision=12,
        )

    original_sha = publish_deployment_gitops(
        repository_url=str(remote),
        spec=spec("v12"),
    )

    assert original_sha is not None

    with pytest.raises(ConflictingGitOpsRevisionError):
        publish_deployment_gitops(
            repository_url=str(remote),
            spec=spec("v12-modified"),
        )

    verify = tmp_path / "verify"
    git("clone", str(remote), str(verify))

    values_path = (
        verify
        / "gitops"
        / "apps"
        / "dev"
        / str(project_id)
        / "test-api"
        / "values.yaml"
    )

    values = yaml.safe_load(values_path.read_text())

    assert values["deployment"]["revision"] == 12
    assert values["image"]["tag"] == "v12"
    assert git("rev-parse", "HEAD", cwd=verify) == original_sha
