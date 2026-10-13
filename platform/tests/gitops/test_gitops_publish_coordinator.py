import subprocess
from pathlib import Path
from uuid import uuid4
from unittest.mock import patch

from afterpush_api.services.gitops_publish_coordinator import (
    publish_with_retry,
)
from afterpush_api.services.gitops_push import (
    push_gitops_commit,
)


def git(*args) -> str:
    result = subprocess.run(
        ["git", *map(str, args)],
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout.strip()


def configure_git(repository: Path) -> None:
    git("-C", repository, "config", "user.name", "AfterPush Test")
    git(
        "-C",
        repository,
        "config",
        "user.email",
        "test@afterpush.local",
    )


def test_retries_after_concurrent_push(tmp_path):
    remote = tmp_path / "remote.git"
    seed = tmp_path / "seed"

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

    project_id = str(uuid4())
    attempts = []
    real_push = push_gitops_commit

    def prepare_values(workspace: Path) -> Path:
        attempts.append(workspace)

        path = (
            workspace
            / "gitops"
            / "apps"
            / "staging"
            / project_id
            / "payment-api"
            / "values.yaml"
        )

        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            "image:\n  tag: v2\n",
            encoding="utf-8",
        )
        return path

    def competing_push(workspace: Path) -> str:
        if len(attempts) == 1:
            competitor = tmp_path / "competitor"
            git("clone", "--branch", "main", remote, competitor)
            configure_git(competitor)

            competitor_values = (
                competitor
                / "gitops"
                / "apps"
                / "staging"
                / project_id
                / "auth-api"
                / "values.yaml"
            )

            competitor_values.parent.mkdir(
                parents=True,
                exist_ok=True,
            )
            competitor_values.write_text(
                "image:\n  tag: v3\n",
                encoding="utf-8",
            )

            git("-C", competitor, "add", ".")
            git(
                "-C",
                competitor,
                "commit",
                "-m",
                "Deploy auth-api",
            )
            git("-C", competitor, "push", "origin", "HEAD:main")

        return real_push(workspace)

    with patch(
        "afterpush_api.services.gitops_publish_coordinator.push_gitops_commit",
        side_effect=competing_push,
    ):
        published_sha = publish_with_retry(
            repository_url=str(remote),
            prepare_values=prepare_values,
            commit_message="Deploy payment-api",
        )

    assert published_sha is not None
    assert len(attempts) == 2

    verification = tmp_path / "verification"
    git("clone", "--branch", "main", remote, verification)

    apps_directory = (
        verification
        / "gitops"
        / "apps"
        / "staging"
        / project_id
    )

    assert (
        apps_directory / "payment-api" / "values.yaml"
    ).is_file()

    assert (
        apps_directory / "auth-api" / "values.yaml"
    ).is_file()

    assert published_sha == git(
        "-C", verification, "rev-parse", "HEAD"
    )
