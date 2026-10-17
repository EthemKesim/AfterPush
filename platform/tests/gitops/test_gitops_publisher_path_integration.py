import subprocess
from pathlib import Path

import pytest

from afterpush_api.services.gitops_publisher import (
    GitOpsPublishError,
    publish_gitops_file,
)


PROJECT_ID = "12471cf9-11d4-4089-ad0d-2c4b777fc227"


def git(repository: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(repository), *args],
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


@pytest.fixture
def repository(tmp_path):
    root = tmp_path / "repository"
    root.mkdir()

    git(root, "init")
    git(root, "config", "user.name", "AfterPush Test")
    git(root, "config", "user.email", "test@example.com")

    (root / "README.md").write_text("initial\n")

    git(root, "add", "README.md")
    git(root, "commit", "-m", "initial")

    return root


@pytest.mark.parametrize(
    "relative_path",
    [
        "gitops/apps/dev/not-a-uuid/payment-api/values.yaml",
        f"gitops/apps/dev/{PROJECT_ID}/Payment_API/values.yaml",
        f"gitops/apps/test/{PROJECT_ID}/payment-api/values.yaml",
        f"gitops/platform/namespaces/dev/not-a-uuid/namespace.yaml",
    ],
)
def test_invalid_path_never_stages_or_commits(
    repository,
    relative_path,
):
    target = repository / relative_path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("test: value\n")

    original_head = git(repository, "rev-parse", "HEAD")

    with pytest.raises(GitOpsPublishError):
        publish_gitops_file(
            repository_root=repository,
            values_path=target,
            commit_message="unsafe publication",
        )

    assert git(repository, "rev-parse", "HEAD") == original_head
    assert git(repository, "diff", "--cached", "--name-only") == ""


def test_valid_deployment_path_can_commit(repository):
    target = (
        repository
        / f"gitops/apps/dev/{PROJECT_ID}/payment-api/values.yaml"
    )

    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("image:\n  tag: test\n")

    commit_sha = publish_gitops_file(
        repository_root=repository,
        values_path=target,
        commit_message="valid deployment",
    )

    assert commit_sha == git(repository, "rev-parse", "HEAD")
    assert git(repository, "show", "--format=", "--name-only", "HEAD") == (
        f"gitops/apps/dev/{PROJECT_ID}/payment-api/values.yaml"
    )
