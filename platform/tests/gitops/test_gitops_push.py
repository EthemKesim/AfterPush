import subprocess
from pathlib import Path

import pytest

from afterpush_api.services.gitops_push import (
    GitOpsPushError,
    push_gitops_commit,
)


def git(*args: str) -> str:
    result = subprocess.run(
        ["git", *map(str, args)],
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout.strip()


def configure_git(repository: Path) -> None:
    git("-C", repository, "config", "user.name", "AfterPush Bot")
    git(
        "-C",
        repository,
        "config",
        "user.email",
        "afterpush-bot@example.com",
    )


@pytest.fixture
def repositories(tmp_path):
    remote = tmp_path / "remote.git"
    seed = tmp_path / "seed"
    worker_a = tmp_path / "worker-a"
    worker_b = tmp_path / "worker-b"

    git("init", "--bare", "--initial-branch=main", remote)
    git("clone", remote, seed)

    configure_git(seed)

    (seed / "README.md").write_text(
        "# AfterPush\n",
        encoding="utf-8",
    )

    git("-C", seed, "add", "README.md")
    git("-C", seed, "commit", "-m", "Initial commit")
    git("-C", seed, "push", "origin", "HEAD:main")

    git("clone", "--branch", "main", remote, worker_a)
    git("clone", "--branch", "main", remote, worker_b)

    configure_git(worker_a)
    configure_git(worker_b)

    return remote, worker_a, worker_b


def create_commit(repository: Path, filename: str) -> str:
    file_path = repository / filename
    file_path.write_text(
        f"Content for {filename}\n",
        encoding="utf-8",
    )

    git("-C", repository, "add", filename)
    git("-C", repository, "commit", "-m", f"Add {filename}")

    return git("-C", repository, "rev-parse", "HEAD")


def test_pushes_commit_to_remote_main(repositories):
    remote, worker_a, _ = repositories

    commit_sha = create_commit(worker_a, "deployment-a.txt")

    pushed_sha = push_gitops_commit(worker_a)

    remote_sha = git(
        "--git-dir",
        remote,
        "rev-parse",
        "refs/heads/main",
    )

    assert pushed_sha == commit_sha
    assert remote_sha == commit_sha


def test_rejects_push_when_remote_has_advanced(repositories):
    remote, worker_a, worker_b = repositories

    first_commit = create_commit(
        worker_a,
        "deployment-a.txt",
    )

    push_gitops_commit(worker_a)

    create_commit(worker_b, "deployment-b.txt")

    with pytest.raises(GitOpsPushError):
        push_gitops_commit(worker_b)

    remote_sha = git(
        "--git-dir",
        remote,
        "rev-parse",
        "refs/heads/main",
    )

    assert remote_sha == first_commit


def test_rejects_non_main_branch(repositories):
    _, worker_a, _ = repositories

    with pytest.raises(
        GitOpsPushError,
        match="restricted to main",
    ):
        push_gitops_commit(
            worker_a,
            branch="development",
        )
