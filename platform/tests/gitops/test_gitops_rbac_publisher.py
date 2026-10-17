import subprocess
from pathlib import Path
from uuid import uuid4

import pytest

from afterpush_api.services.gitops_rbac_publisher import (
    publish_gitops_rbac_files,
    GitOpsRBACPublishError,
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


@pytest.fixture
def rbac_files(repository):
    project_id = uuid4()

    directory = (
        repository
        / "gitops"
        / "platform"
        / "rbac"
        / "projects"
        / "dev"
        / str(project_id)
        / "payment-api"
    )

    directory.mkdir(parents=True)

    argocd = directory / "argocd-rbac.yaml"
    deployment = directory / "deployment-rbac.yaml"

    argocd.write_text(
        "kind: Role\nmetadata:\n  name: argocd-reader\n",
        encoding="utf-8",
    )
    deployment.write_text(
        "kind: Role\nmetadata:\n  name: deployment-reader\n",
        encoding="utf-8",
    )

    return argocd, deployment


def test_publishes_both_rbac_files_in_one_commit(
    repository,
    rbac_files,
):
    commit_sha = publish_gitops_rbac_files(
        repository_root=repository,
        rbac_paths=rbac_files,
        commit_message="Configure observer RBAC",
    )

    assert commit_sha == git(repository, "rev-parse", "HEAD")

    committed = git(
        repository,
        "diff-tree",
        "--no-commit-id",
        "--name-only",
        "-r",
        "HEAD",
    ).splitlines()

    expected = sorted(
        path.relative_to(repository).as_posix()
        for path in rbac_files
    )

    assert sorted(committed) == expected


def test_no_commit_when_rbac_unchanged(
    repository,
    rbac_files,
):
    first = publish_gitops_rbac_files(
        repository,
        rbac_files,
        "Initial RBAC",
    )

    second = publish_gitops_rbac_files(
        repository,
        rbac_files,
        "Duplicate RBAC",
    )

    assert first is not None
    assert second is None
    assert git(repository, "rev-parse", "HEAD") == first


def test_rejects_unrelated_file(repository, rbac_files):
    with pytest.raises(GitOpsRBACPublishError):
        publish_gitops_rbac_files(
            repository,
            (rbac_files[0], repository / "README.md"),
            "Invalid RBAC",
        )


def test_rejects_previously_staged_changes(
    repository,
    rbac_files,
):
    (repository / "README.md").write_text(
        "# Staged change\n",
        encoding="utf-8",
    )
    git(repository, "add", "README.md")

    with pytest.raises(
        GitOpsRBACPublishError,
        match="Git index must be clean",
    ):
        publish_gitops_rbac_files(
            repository,
            rbac_files,
            "Configure RBAC",
        )


def test_rejects_missing_rbac_file(
    repository,
    rbac_files,
):
    rbac_files[1].unlink()

    with pytest.raises(GitOpsRBACPublishError):
        publish_gitops_rbac_files(
            repository,
            rbac_files,
            "Configure RBAC",
        )


def test_rejects_duplicate_rbac_paths(
    repository,
    rbac_files,
):
    with pytest.raises(GitOpsRBACPublishError):
        publish_gitops_rbac_files(
            repository,
            (rbac_files[0], rbac_files[0]),
            "Invalid RBAC",
        )


@pytest.mark.parametrize(
    "application_name",
    [
        "Payment API",
        "payment_api",
        ".hidden",
        "payment--api",
    ],
)
def test_rejects_invalid_application_names(
    repository,
    application_name,
):
    directory = (
        repository
        / "gitops"
        / "platform"
        / "rbac"
        / "projects"
        / "dev"
        / str(uuid4())
        / application_name
    )
    directory.mkdir(parents=True)

    paths = (
        directory / "argocd-rbac.yaml",
        directory / "deployment-rbac.yaml",
    )

    for path in paths:
        path.write_text("kind: Role\n", encoding="utf-8")

    with pytest.raises(GitOpsRBACPublishError):
        publish_gitops_rbac_files(
            repository,
            paths,
            "Invalid application name",
        )


def test_rejects_noncanonical_project_uuid(repository):
    project_id = str(uuid4()).upper()

    directory = (
        repository
        / "gitops"
        / "platform"
        / "rbac"
        / "projects"
        / "dev"
        / project_id
        / "payment-api"
    )
    directory.mkdir(parents=True)

    paths = (
        directory / "argocd-rbac.yaml",
        directory / "deployment-rbac.yaml",
    )

    for path in paths:
        path.write_text("kind: Role\n", encoding="utf-8")

    with pytest.raises(GitOpsRBACPublishError):
        publish_gitops_rbac_files(
            repository,
            paths,
            "Invalid project ID",
        )
