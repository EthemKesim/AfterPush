import subprocess
from pathlib import Path


class GitOpsPublishError(Exception):
    """Raised when a GitOps publishing operation fails."""


def run_git(
    repository_root: Path,
    *arguments: str,
) -> str:
    """Run a Git command without invoking a shell."""

    result = subprocess.run(
        ["git", "-C", str(repository_root), *arguments],
        capture_output=True,
        text=True,
        check=False,
    )

    if result.returncode != 0:
        raise GitOpsPublishError(
            f"Git command failed: {' '.join(arguments)}\n"
            f"{result.stderr.strip()}"
        )

    return result.stdout.strip()


def publish_gitops_file(
    repository_root: Path,
    values_path: Path,
    commit_message: str,
) -> str | None:
    """
    Commit one GitOps values file in an isolated repository.

    The caller must supply a dedicated Git working tree.
    This function does not push to a remote.
    """

    repository_root = Path(repository_root).resolve()
    values_path = Path(values_path).resolve()

    if not repository_root.is_dir():
        raise GitOpsPublishError(
            "Git repository directory does not exist."
        )

    try:
        relative_path = values_path.relative_to(repository_root)
    except ValueError as exc:
        raise GitOpsPublishError(
            "GitOps values file is outside the repository."
        ) from exc

    parts = relative_path.parts

    if (
        len(parts) != 6
        or parts[0] != "gitops"
        or parts[1] != "apps"
        or parts[-1] != "values.yaml"
    ):
        raise GitOpsPublishError(
            "Only project-scoped GitOps values.yaml files can be published."
        )

    if not values_path.is_file():
        raise GitOpsPublishError(
            "GitOps values file does not exist."
        )

    actual_root = Path(
        run_git(repository_root, "rev-parse", "--show-toplevel")
    ).resolve()

    if actual_root != repository_root:
        raise GitOpsPublishError(
            "Repository root does not match the supplied directory."
        )

    if run_git(repository_root, "diff", "--cached", "--name-only"):
        raise GitOpsPublishError(
            "Git index must be clean before publishing."
        )

    run_git(
        repository_root,
        "add",
        "--",
        relative_path.as_posix(),
    )

    staged_files = run_git(
        repository_root,
        "diff",
        "--cached",
        "--name-only",
    ).splitlines()

    if not staged_files:
        return None

    if staged_files != [relative_path.as_posix()]:
        raise GitOpsPublishError(
            "Unexpected files were staged."
        )

    run_git(
        repository_root,
        "commit",
        "-m",
        commit_message,
        "--",
        relative_path.as_posix(),
    )

    return run_git(repository_root, "rev-parse", "HEAD")
