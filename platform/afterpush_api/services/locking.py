
import fcntl
from contextlib import contextmanager
from pathlib import Path
from uuid import UUID

from afterpush_api.services.gitops import (
    InvalidGitOpsPathError,
    validate_name,
    validate_project_id,
)


@contextmanager
def gitops_application_lock(
    gitops_root: Path,
    application_name: str,
    environment: str,
    project_id: UUID | None = None,
):
    """
    Acquire an exclusive lock for one application/environment.

    When project_id is provided, locks are isolated by project.

    Cooperating processes on the same filesystem use this lock
    to serialize GitOps configuration changes.
    """

    validate_name(application_name)
    validate_name(environment)
    validate_project_id(project_id)

    root = Path(gitops_root)

    if root.is_symlink():
        raise InvalidGitOpsPathError(
            f"GitOps root cannot be a symlink: {root}"
        )

    lock_directory = root / ".locks"

    if lock_directory.is_symlink():
        raise InvalidGitOpsPathError(
            f"GitOps lock directory cannot be a symlink: {lock_directory}"
        )

    lock_directory.mkdir(
        parents=True,
        exist_ok=True,
    )

    if project_id is None:
        lock_filename = (
            f"{environment}--{application_name}.lock"
        )
    else:
        lock_filename = (
            f"{environment}--{project_id}--"
            f"{application_name}.lock"
        )

    lock_path = lock_directory / lock_filename

    if lock_path.is_symlink():
        raise InvalidGitOpsPathError(
            f"GitOps lock file cannot be a symlink: {lock_path}"
        )

    with lock_path.open("a+") as lock_file:
        fcntl.flock(
            lock_file.fileno(),
            fcntl.LOCK_EX,
        )

        try:
            yield
        finally:
            fcntl.flock(
                lock_file.fileno(),
                fcntl.LOCK_UN,
            )
