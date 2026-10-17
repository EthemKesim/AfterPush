from pathlib import Path

from afterpush_api.services.gitops_rbac_cleanup import (
    RBACCleanupCandidate,
)
from afterpush_api.services.gitops_rbac_cleanup_git import (
    verify_tracked_rbac_candidate,
)
from afterpush_api.services.gitops_rbac_validator import (
    validate_gitops_rbac,
)


def verify_cleanup_candidate(
    *,
    repository_root: Path,
    candidate: RBACCleanupCandidate,
) -> bool:
    """
    Verify Git tracking and expected RBAC manifest contents.

    Read-only: never deletes, stages, commits or pushes.
    """
    repository_root = Path(repository_root).resolve()

    if not verify_tracked_rbac_candidate(
        repository_root=repository_root,
        candidate=candidate,
    ):
        return False

    directory = repository_root / candidate.relative_directory

    rbac_paths = (
        directory / "argocd-rbac.yaml",
        directory / "deployment-rbac.yaml",
    )

    try:
        validate_gitops_rbac(
            rbac_paths=rbac_paths,
            project_id=candidate.target.project_id,
            application_name=candidate.target.application_name,
            environment=candidate.target.environment,
        )
    except (ValueError, TypeError, OSError):
        return False

    return True
