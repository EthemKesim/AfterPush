from dataclasses import dataclass
from pathlib import Path
from uuid import UUID

from afterpush_api.services.gitops_rbac_selection import (
    RBACPublicationTarget,
)


RBAC_ROOT = Path("gitops/platform/rbac/projects")
VALID_ENVIRONMENTS = {"dev", "staging", "prod"}
EXPECTED_FILES = {
    "argocd-rbac.yaml",
    "deployment-rbac.yaml",
}


@dataclass(frozen=True)
class RBACCleanupCandidate:
    target: RBACPublicationTarget
    relative_directory: Path


def find_orphaned_rbac(
    *,
    repository_root: Path,
    valid_targets: set[RBACPublicationTarget],
) -> list[RBACCleanupCandidate]:
    """
    Identify RBAC directories without a matching published target.

    Read-only: does not delete files, commit, push or modify
    Kubernetes resources.
    """
    repository_root = Path(repository_root).resolve()

    if not repository_root.is_dir():
        raise ValueError("Repository directory does not exist")

    rbac_root = repository_root / RBAC_ROOT

    if not rbac_root.exists():
        return []

    if rbac_root.is_symlink() or not rbac_root.is_dir():
        raise ValueError("Invalid RBAC root directory")

    candidates = []

    for environment_dir in sorted(rbac_root.iterdir()):
        if (
            environment_dir.is_symlink()
            or not environment_dir.is_dir()
            or environment_dir.name not in VALID_ENVIRONMENTS
        ):
            continue

        for project_dir in sorted(environment_dir.iterdir()):
            if project_dir.is_symlink() or not project_dir.is_dir():
                continue

            try:
                project_id = UUID(project_dir.name)
            except ValueError:
                continue

            if str(project_id) != project_dir.name:
                continue

            for application_dir in sorted(project_dir.iterdir()):
                if (
                    application_dir.is_symlink()
                    or not application_dir.is_dir()
                ):
                    continue

                filenames = {
                    path.name for path in application_dir.iterdir()
                    if path.is_file() and not path.is_symlink()
                }

                if filenames != EXPECTED_FILES:
                    continue

                target = RBACPublicationTarget(
                    project_id=project_id,
                    application_name=application_dir.name,
                    environment=environment_dir.name,
                )

                if target not in valid_targets:
                    candidates.append(
                        RBACCleanupCandidate(
                            target=target,
                            relative_directory=(
                                application_dir.relative_to(
                                    repository_root
                                )
                            ),
                        )
                    )

    return candidates
