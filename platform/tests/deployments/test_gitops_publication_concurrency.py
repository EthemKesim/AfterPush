import subprocess
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from uuid import uuid4

import pytest
import yaml

from afterpush_api.services.deployment_gitops import (
    DeploymentGitOpsSpec,
)
from afterpush_api.services.deployment_publication import (
    publish_deployment_gitops,
)
from afterpush_api.services.gitops_revision import (
    StaleGitOpsRevisionError,
)


def git(*args, cwd=None):
    return subprocess.run(
        ["git", *args],
        cwd=cwd,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def test_concurrent_revisions_preserve_newest(tmp_path):
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
    barrier = Barrier(2)

    def publish(revision):
        spec = DeploymentGitOpsSpec(
            application_name="test-api",
            environment="dev",
            image_repository="example/test-api",
            image_tag=f"v{revision}",
            port=3000,
            replicas=2,
            project_id=project_id,
            revision=revision,
        )

        barrier.wait(timeout=10)

        try:
            return publish_deployment_gitops(
                repository_url=str(remote),
                spec=spec,
                max_attempts=5,
            )
        except StaleGitOpsRevisionError:
            return "stale"

    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [
            executor.submit(publish, 11),
            executor.submit(publish, 12),
        ]
        results = [future.result() for future in futures]

    assert any(
        result not in (None, "stale")
        for result in results
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
