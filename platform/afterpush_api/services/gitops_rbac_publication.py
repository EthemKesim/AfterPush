from pathlib import Path
from uuid import UUID

from afterpush_api.services.gitops_publish_coordinator import (
    run_git,
)
from afterpush_api.services.gitops_push import (
    GitOpsPushConflictError,
    push_gitops_commit,
)
from afterpush_api.services.gitops_rbac_preparation import (
    prepare_gitops_rbac,
)
from afterpush_api.services.gitops_rbac_publisher import (
    publish_gitops_rbac_files,
)
from afterpush_api.services.gitops_rbac_validator import (
    validate_gitops_rbac,
)
from afterpush_api.services.gitops_workspace import (
    isolated_gitops_workspace,
)


class GitOpsRBACRetryExhausted(Exception):
    """Raised when all RBAC push attempts conflict."""


def publish_rbac_with_retry(
    *,
    repository_url: str,
    project_id: UUID,
    application_name: str,
    environment: str,
    max_attempts: int = 3,
) -> str:
    """
    Publish project observer RBAC to GitOps main.

    Returns the pushed commit SHA, or HEAD when unchanged.

    Only non-fast-forward push conflicts are retried.
    Does not apply resources to Kubernetes.
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

            rbac_paths = prepare_gitops_rbac(
                repository_root=workspace,
                project_id=project_id,
                application_name=application_name,
                environment=environment,
            )

            validate_gitops_rbac(
                rbac_paths=rbac_paths,
                project_id=project_id,
                application_name=application_name,
                environment=environment,
            )

            commit_sha = publish_gitops_rbac_files(
                repository_root=workspace,
                rbac_paths=rbac_paths,
                commit_message=(
                    f"rbac({environment}): "
                    f"configure observer for {application_name}"
                ),
            )

            if commit_sha is None:
                return run_git(
                    workspace,
                    "rev-parse",
                    "HEAD",
                )

            try:
                return push_gitops_commit(workspace)
            except GitOpsPushConflictError as exc:
                if attempt == max_attempts:
                    raise GitOpsRBACRetryExhausted(
                        "RBAC GitOps push conflicted after "
                        f"{max_attempts} attempts."
                    ) from exc

    raise GitOpsRBACRetryExhausted(
        "RBAC GitOps publication did not complete."
    )
