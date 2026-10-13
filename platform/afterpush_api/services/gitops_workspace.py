import subprocess
import tempfile
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator


class GitOpsWorkspaceError(Exception):
    """Raised when an isolated GitOps workspace cannot be created."""


@contextmanager
def isolated_gitops_workspace(
    repository_url: str,
    branch: str = "main",
) -> Iterator[Path]:
    """
    Clone a specific branch into an isolated temporary directory.

    The temporary directory is removed automatically when
    the context manager exits, including on exceptions.

    No commits or pushes are performed by this function.
    """

    if not repository_url:
        raise GitOpsWorkspaceError(
            "Repository URL cannot be empty."
        )

    if not branch:
        raise GitOpsWorkspaceError(
            "Git branch cannot be empty."
        )

    with tempfile.TemporaryDirectory(
        prefix="afterpush-gitops-"
    ) as temporary_directory:
        workspace = Path(temporary_directory) / "repository"

        result = subprocess.run(
            [
                "git",
                "-c",
                "credential.interactive=never",
                "clone",
                "--quiet",
                "--single-branch",
                "--branch",
                branch,
                "--",
                repository_url,
                str(workspace),
            ],
            capture_output=True,
            text=True,
            check=False,
            timeout=60,
        )

        if result.returncode != 0:
            raise GitOpsWorkspaceError(
                "Unable to create isolated GitOps workspace: "
                + result.stderr.strip()
            )

        yield workspace
