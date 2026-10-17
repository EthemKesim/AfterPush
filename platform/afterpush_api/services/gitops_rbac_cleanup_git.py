import subprocess
from pathlib import Path

from afterpush_api.services.gitops_rbac_cleanup import (
    RBACCleanupCandidate,
)


EXPECTED_FILES = (
    "argocd-rbac.yaml",
    "deployment-rbac.yaml",
)


def verify_tracked_rbac_candidate(
    *,
    repository_root: Path,
    candidate: RBACCleanupCandidate,
) -> bool:
    """
    Verify both RBAC manifests exist in the current Git HEAD.

    Read-only. Does not stage, delete, commit or push.
    """
    repository_root = Path(repository_root).resolve()
    relative_directory = candidate.relative_directory

    expected_directory = (
        Path("gitops/platform/rbac/projects")
        / candidate.target.environment
        / str(candidate.target.project_id)
        / candidate.target.application_name
    )

    if relative_directory != expected_directory:
        return False

    for filename in EXPECTED_FILES:
        relative_file = relative_directory / filename
        absolute_file = repository_root / relative_file

        if absolute_file.is_symlink() or not absolute_file.is_file():
            return False

        result = subprocess.run(
            [
                "git",
                "-C",
                str(repository_root),
                "cat-file",
                "-e",
                f"HEAD:{relative_file.as_posix()}",
            ],
            capture_output=True,
            text=True,
            check=False,
            timeout=10,
        )

        if result.returncode != 0:
            return False

        # Accept only regular files recorded in Git HEAD.
        mode_result = subprocess.run(
            [
                "git",
                "-C",
                str(repository_root),
                "ls-tree",
                "HEAD",
                "--",
                str(relative_file),
            ],
            capture_output=True,
            text=True,
            check=False,
            timeout=10,
        )

        if mode_result.returncode != 0:
            return False

        expected_entry = (
            f"100644 blob "
        )

        if not mode_result.stdout.startswith(expected_entry):
            return False

        # Reject staged or unstaged changes relative to HEAD.
        diff_result = subprocess.run(
            [
                "git",
                "-C",
                str(repository_root),
                "diff",
                "--quiet",
                "HEAD",
                "--",
                str(relative_file),
            ],
            capture_output=True,
            text=True,
            check=False,
            timeout=10,
        )

        if diff_result.returncode != 0:
            return False

    return True
