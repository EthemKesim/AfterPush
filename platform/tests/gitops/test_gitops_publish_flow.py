import subprocess
from pathlib import Path
from uuid import uuid4

from afterpush_api.services.gitops_publisher import (
    publish_gitops_file,
)
from afterpush_api.services.gitops_workspace import (
    isolated_gitops_workspace,
)


def git(repository: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(repository), *args],
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout.strip()


def test_isolated_gitops_publish_flow(tmp_path):
    source = tmp_path / "source"
    source.mkdir()

    git(source, "init", "-b", "main")
    git(source, "config", "user.name", "AfterPush Test")
    git(source, "config", "user.email", "test@afterpush.local")

    (source / "README.md").write_text(
        "# AfterPush\n",
        encoding="utf-8",
    )

    git(source, "add", "README.md")
    git(source, "commit", "-m", "Initial commit")

    project_id = uuid4()

    with isolated_gitops_workspace(str(source)) as workspace:
        git(workspace, "config", "user.name", "AfterPush Publisher")
        git(workspace, "config", "user.email", "publisher@afterpush.local")

        values_path = (
            workspace
            / "gitops"
            / "apps"
            / "staging"
            / str(project_id)
            / "payment-api"
            / "values.yaml"
        )

        values_path.parent.mkdir(parents=True)

        values_path.write_text(
            "image:\n"
            "  repository: nginx\n"
            "  tag: v2.0.0\n",
            encoding="utf-8",
        )

        commit_sha = publish_gitops_file(
            repository_root=workspace,
            values_path=values_path,
            commit_message="Deploy payment-api v2.0.0",
        )

        assert commit_sha is not None
        assert commit_sha == git(workspace, "rev-parse", "HEAD")

        committed_files = git(
            workspace,
            "diff-tree",
            "--no-commit-id",
            "--name-only",
            "-r",
            "HEAD",
        ).splitlines()

        assert committed_files == [
            values_path.relative_to(workspace).as_posix()
        ]

        workspace_path = workspace

    assert not workspace_path.exists()

    # Publishing locally must not modify the source repository.
    assert git(source, "status", "--short") == ""
    assert not (source / "gitops").exists()
