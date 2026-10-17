import subprocess
from pathlib import Path
from typing import Callable

from afterpush_api.services.gitops_publisher import (
    publish_gitops_file,
)
from afterpush_api.services.gitops_push import (
    GitOpsPushConflictError,
    push_gitops_commit,
)
from afterpush_api.services.gitops_workspace import (
    isolated_gitops_workspace,
)


class GitOpsPublishRetryExhausted(Exception):
    """Raised when all GitOps publication attempts conflict."""


def run_git(repository_root: Path, *arguments: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(repository_root), *arguments],
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def publish_with_retry(
    repository_url: str,
    prepare_values: Callable[[Path], Path],
    commit_message: str,
    max_attempts: int = 3,
    validate_content: Callable[[Path], None] | None = None,
) -> str:
    """
    Publish GitOps changes from a fresh main checkout.

    Returns the pushed commit SHA, or the current HEAD SHA
    when the requested values already match the checkout.

    Only non-fast-forward push conflicts are retried.
    """

    if max_attempts < 1:
        raise ValueError("max_attempts must be at least 1")

    for attempt in range(1, max_attempts + 1):
        with isolated_gitops_workspace(
            repository_url,
            branch="main",
        ) as workspace:
            run_git(
                workspace,
                "config",
                "user.name",
                "AfterPush Bot",
            )
            run_git(
                workspace,
                "config",
                "user.email",
                "afterpush-bot@users.noreply.github.com",
            )

            values_path = prepare_values(workspace)

            commit_sha = publish_gitops_file(
                repository_root=workspace,
                values_path=values_path,
                commit_message=commit_message,
                validate_content=validate_content,
            )

            if commit_sha is None:
                return run_git(workspace, "rev-parse", "HEAD")

            try:
                return push_gitops_commit(workspace)
            except GitOpsPushConflictError as exc:
                if attempt == max_attempts:
                    raise GitOpsPublishRetryExhausted(
                        f"GitOps push conflicted after "
                        f"{max_attempts} attempts."
                    ) from exc

    raise GitOpsPublishRetryExhausted(
        "GitOps publication did not complete."
    )
