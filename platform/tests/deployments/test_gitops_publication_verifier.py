import subprocess
from dataclasses import replace
from uuid import uuid4

import pytest

from afterpush_api.services.deployment_gitops import (
    DeploymentGitOpsSpec,
)
from afterpush_api.services.deployment_publication import (
    publish_deployment_gitops,
)
from afterpush_api.services.gitops_publication_verifier import (
    verify_gitops_publication,
)


def git(*args, cwd=None):
    return subprocess.run(
        ["git", *args],
        cwd=cwd,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


@pytest.fixture
def published_gitops(tmp_path):
    remote = tmp_path / "gitops.git"
    git("init", "--bare", "--initial-branch=main", str(remote))

    seed = tmp_path / "seed"
    git("clone", str(remote), str(seed))
    git("config", "user.name", "AfterPush Test", cwd=seed)
    git("config", "user.email", "test@afterpush.local", cwd=seed)

    (seed / "README.md").write_text("AfterPush verifier test\n")
    git("add", "README.md", cwd=seed)
    git("commit", "-m", "Initial commit", cwd=seed)
    git("push", "origin", "HEAD:refs/heads/main", cwd=seed)

    spec = DeploymentGitOpsSpec(
        application_name="verifier-api",
        environment="dev",
        image_repository="example/verifier-api",
        image_tag="v12",
        port=3000,
        replicas=2,
        project_id=uuid4(),
        revision=12,
    )

    published_sha = publish_deployment_gitops(
        repository_url=str(remote),
        spec=spec,
    )

    assert published_sha is not None

    return str(remote), spec, published_sha


def test_verifier_accepts_matching_publication(published_gitops):
    remote, spec, published_sha = published_gitops

    result = verify_gitops_publication(remote, spec)

    assert result.matches is True
    assert result.observed_revision == 12
    assert result.commit_sha == published_sha


def test_verifier_rejects_different_image(published_gitops):
    remote, spec, _ = published_gitops

    different_image = replace(
        spec,
        image_tag="v12-modified",
    )

    result = verify_gitops_publication(remote, different_image)

    assert result.matches is False
    assert result.observed_revision == 12
    assert result.commit_sha is None


def test_verifier_rejects_older_revision(published_gitops):
    remote, spec, _ = published_gitops

    older_revision = replace(
        spec,
        revision=11,
    )

    result = verify_gitops_publication(remote, older_revision)

    assert result.matches is False
    assert result.observed_revision == 12
    assert result.commit_sha is None
