import subprocess
from pathlib import Path

from afterpush_api.services.gitops_workspace import (
    isolated_gitops_workspace,
)


def test_workspace_is_isolated_and_cleaned_up(tmp_path):
    source = tmp_path / "source"
    source.mkdir()

    subprocess.run(
        ["git", "init", "-b", "main", str(source)],
        check=True,
        capture_output=True,
    )

    subprocess.run(
        ["git", "-C", str(source), "config", "user.name", "AfterPush Test"],
        check=True,
    )

    subprocess.run(
        ["git", "-C", str(source), "config", "user.email", "test@afterpush.local"],
        check=True,
    )

    (source / "README.md").write_text(
        "# AfterPush\n",
        encoding="utf-8",
    )

    subprocess.run(
        ["git", "-C", str(source), "add", "README.md"],
        check=True,
    )

    subprocess.run(
        ["git", "-C", str(source), "commit", "-m", "Initial commit"],
        check=True,
        capture_output=True,
    )

    with isolated_gitops_workspace(str(source)) as workspace:
        workspace_path = Path(workspace)

        assert workspace_path.exists()
        assert (workspace_path / "README.md").is_file()

        branch = subprocess.run(
            ["git", "-C", str(workspace_path), "branch", "--show-current"],
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()

        assert branch == "main"

    assert not workspace_path.exists()
