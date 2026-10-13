import subprocess
from pathlib import Path


class GitOpsPushError(Exception):
    """Raised when GitOps push fails."""


class GitOpsPushConflictError(GitOpsPushError):
    """Raised when the remote branch has advanced."""


def push_gitops_commit(
    repository_root: Path,
    branch: str = "main",
) -> str:
    """
    Push an existing GitOps commit to origin/main.

    Never uses force push.
    """

    if branch != "main":
        raise GitOpsPushError(
            "GitOps publishing is restricted to main."
        )

    repository_root = Path(repository_root).resolve()

    result = subprocess.run(
        [
            "git",
            "-C",
            str(repository_root),
            "-c",
            "credential.interactive=never",
            "push",
            "origin",
            "HEAD:refs/heads/main",
        ],
        capture_output=True,
        text=True,
        check=False,
        timeout=60,
    )

    if result.returncode != 0:
        stderr = result.stderr.strip()
        normalized_error = stderr.lower()

        non_fast_forward = (
            "[rejected]" in normalized_error
            and (
                "fetch first" in normalized_error
                or "non-fast-forward" in normalized_error
            )
        )

        concurrent_ref_update = (
            "cannot lock ref 'refs/heads/main'"
            in normalized_error
            and "is at" in normalized_error
            and "but expected" in normalized_error
        )

        if non_fast_forward or concurrent_ref_update:
            raise GitOpsPushConflictError(
                "Remote main has advanced: " + stderr
            )

        raise GitOpsPushError(
            "GitOps push failed: " + stderr
        )

    revision = subprocess.run(
        [
            "git",
            "-C",
            str(repository_root),
            "rev-parse",
            "HEAD",
        ],
        capture_output=True,
        text=True,
        check=True,
    )

    return revision.stdout.strip()
