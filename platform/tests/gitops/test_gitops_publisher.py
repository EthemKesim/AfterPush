import subprocess
from pathlib import Path
from uuid import uuid4

import pytest

from afterpush_api.services.gitops_publisher import (
    GitOpsPublishError,
    publish_gitops_file,
)


def git(repo: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(repo), *args],
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout.strip()


@pytest.fixture
def repository(tmp_path):
    repo = tmp_path / "repository"
    repo.mkdir()

    git(repo, "init")
    git(repo, "config", "user.name", "AfterPush Test")
    git(repo, "config", "user.email", "test@afterpush.local")

    (repo / "README.md").write_text(
        "# AfterPush Test\n",
        encoding="utf-8",
    )

    git(repo, "add", "README.md")
    git(repo, "commit", "-m", "Initial commit")

    return repo


def test_publishes_only_target_values_file(repository):
    project_id = uuid4()

    values_path = (
        repository
        / "gitops"
        / "apps"
        / "staging"
        / str(project_id)
        / "payment-api"
        / "values.yaml"
    )

    values_path.parent.mkdir(parents=True)

    values_path.write_text(
        "image:\n  repository: nginx\n  tag: v1\n",
        encoding="utf-8",
    )

    unrelated_file = repository / "README.md"
    unrelated_file.write_text(
        "# Unrelated change\n",
        encoding="utf-8",
    )

    commit_sha = publish_gitops_file(
        repository_root=repository,
        values_path=values_path,
        commit_message="Deploy payment-api v1",
    )

    assert commit_sha == git(repository, "rev-parse", "HEAD")

    committed_files = git(
        repository,
        "diff-tree",
        "--no-commit-id",
        "--name-only",
        "-r",
        "HEAD",
    ).splitlines()

    assert committed_files == [
        values_path.relative_to(repository).as_posix()
    ]

    assert unrelated_file.read_text(
        encoding="utf-8"
    ) == "# Unrelated change\n"

    assert git(repository, "status", "--short") == "M README.md"


def test_no_commit_when_values_unchanged(repository):
    values_path = (
        repository
        / "gitops"
        / "apps"
        / "staging"
        / str(uuid4())
        / "payment-api"
        / "values.yaml"
    )

    values_path.parent.mkdir(parents=True)

    values_path.write_text(
        "image:\n  tag: v1\n",
        encoding="utf-8",
    )

    first_commit = publish_gitops_file(
        repository,
        values_path,
        "Initial deployment",
    )

    second_commit = publish_gitops_file(
        repository,
        values_path,
        "Duplicate deployment",
    )

    assert first_commit is not None
    assert second_commit is None
    assert git(repository, "rev-parse", "HEAD") == first_commit


def test_rejects_file_outside_gitops_directory(repository):
    outside_file = repository / "README.md"

    with pytest.raises(GitOpsPublishError):
        publish_gitops_file(
            repository,
            outside_file,
            "Invalid deployment",
        )


def test_rejects_previously_staged_changes(repository):
    values_path = (
        repository
        / "gitops"
        / "apps"
        / "staging"
        / str(uuid4())
        / "payment-api"
        / "values.yaml"
    )

    values_path.parent.mkdir(parents=True)

    values_path.write_text(
        "image:\n  tag: v1\n",
        encoding="utf-8",
    )

    (repository / "README.md").write_text(
        "# Staged change\n",
        encoding="utf-8",
    )

    git(repository, "add", "README.md")

    with pytest.raises(
        GitOpsPublishError,
        match="Git index must be clean",
    ):
        publish_gitops_file(
            repository,
            values_path,
            "Deployment",
        )
