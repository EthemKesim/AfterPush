
import fcntl
from contextlib import contextmanager
from pathlib import Path

from afterpush_api.services.gitops import (
    InvalidGitOpsPathError,
    validate_name,
)


@contextmanager
def gitops_application_lock(
    gitops_root: Path,
    application_name: str,
    environment: str,
):
    """
    Acquire an exclusive lock for one application/environment.

    This prevents cooperating processes on the same filesystem
    from modifying the same application's GitOps configuration
    simultaneously.
    """

    validate_name(application_name)
    validate_name(environment)

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

    lock_path = (
        lock_directory
        / f"{environment}--{application_name}.lock"
    )

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
