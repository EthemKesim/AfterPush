import re
from pathlib import Path
from uuid import UUID

from afterpush_api.services.gitops_publisher import (
    GitOpsPublishError,
    run_git,
)


class GitOpsRBACPublishError(GitOpsPublishError):
    """Raised when RBAC publication is invalid or fails."""


EXPECTED_FILENAMES = {
    "argocd-rbac.yaml",
    "deployment-rbac.yaml",
}

APPLICATION_NAME_PATTERN = re.compile(
    r"^[a-z0-9]+(?:-[a-z0-9]+)*$"
)


def publish_gitops_rbac_files(
    repository_root: Path,
    rbac_paths: tuple[Path, Path],
    commit_message: str,
) -> str | None:
    """
    Commit exactly two project-scoped RBAC files.

    Does not push to the remote repository.
    """

    repository_root = Path(repository_root).resolve()

    if not repository_root.is_dir():
        raise GitOpsRBACPublishError(
            "Git repository directory does not exist."
        )

    if len(rbac_paths) != 2:
        raise GitOpsRBACPublishError(
            "Exactly two RBAC files are required."
        )

    relative_paths = []

    for path in rbac_paths:
        resolved_path = Path(path).resolve()

        try:
            relative_path = resolved_path.relative_to(
                repository_root
            )
        except ValueError as exc:
            raise GitOpsRBACPublishError(
                "RBAC file is outside the repository."
            ) from exc

        parts = relative_path.parts

        if (
            len(parts) != 8
            or parts[:4] != (
                "gitops",
                "platform",
                "rbac",
                "projects",
            )
            or parts[-1] not in EXPECTED_FILENAMES
        ):
            raise GitOpsRBACPublishError(
                "Invalid project-scoped RBAC path."
            )

        environment = parts[4]
        project_id = parts[5]
        application_name = parts[6]

        if environment not in {"dev", "staging", "prod"}:
            raise GitOpsRBACPublishError(
                "Invalid RBAC environment."
            )

        try:
            parsed_uuid = UUID(project_id)
        except ValueError as exc:
            raise GitOpsRBACPublishError(
                "Invalid RBAC project ID."
            ) from exc

        if str(parsed_uuid) != project_id:
            raise GitOpsRBACPublishError(
                "Project UUID must use canonical lowercase format."
            )

        if not APPLICATION_NAME_PATTERN.fullmatch(application_name):
            raise GitOpsRBACPublishError(
                "Invalid RBAC application name."
            )

        if not resolved_path.is_file():
            raise GitOpsRBACPublishError(
                "RBAC file does not exist."
            )

        relative_paths.append(relative_path.as_posix())

    if len(set(relative_paths)) != 2:
        raise GitOpsRBACPublishError(
            "Duplicate RBAC paths are not allowed."
        )

    if {
        Path(path).name for path in relative_paths
    } != EXPECTED_FILENAMES:
        raise GitOpsRBACPublishError(
            "Both expected RBAC filenames are required."
        )

    if (
        Path(relative_paths[0]).parent
        != Path(relative_paths[1]).parent
    ):
        raise GitOpsRBACPublishError(
            "RBAC files must belong to the same application."
        )

    actual_root = Path(
        run_git(
            repository_root,
            "rev-parse",
            "--show-toplevel",
        )
    ).resolve()

    if actual_root != repository_root:
        raise GitOpsRBACPublishError(
            "Repository root does not match the supplied directory."
        )

    if run_git(
        repository_root,
        "diff",
        "--cached",
        "--name-only",
    ):
        raise GitOpsRBACPublishError(
            "Git index must be clean before publishing."
        )

    expected_paths = sorted(relative_paths)

    run_git(
        repository_root,
        "add",
        "--",
        *expected_paths,
    )

    staged_paths = sorted(
        run_git(
            repository_root,
            "diff",
            "--cached",
            "--name-only",
        ).splitlines()
    )

    if not staged_paths:
        return None

    if not set(staged_paths).issubset(set(expected_paths)):
        raise GitOpsRBACPublishError(
            "Unexpected files were staged."
        )

    run_git(
        repository_root,
        "commit",
        "-m",
        commit_message,
        "--",
        *expected_paths,
    )

    return run_git(
        repository_root,
        "rev-parse",
        "HEAD",
    )
