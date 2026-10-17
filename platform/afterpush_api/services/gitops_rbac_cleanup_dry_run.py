from dataclasses import dataclass
from pathlib import Path

from sqlalchemy.orm import Session

from afterpush_api.services.gitops_rbac_cleanup import (
    RBACCleanupCandidate,
    find_orphaned_rbac,
)
from afterpush_api.services.gitops_rbac_cleanup_snapshot import (
    collect_rbac_cleanup_protection_snapshot,
)


@dataclass(frozen=True)
class RBACCleanupDryRunResult:
    valid_target_count: int
    orphaned_candidates: tuple[RBACCleanupCandidate, ...]


def plan_rbac_cleanup(
    *,
    db: Session,
    repository_root: Path,
    batch_size: int = 100,
) -> RBACCleanupDryRunResult:
    """
    Generate a read-only RBAC cleanup report.

    Database targets are collected from a consistent snapshot.
    GitOps directories are inspected without modification.
    """
    valid_targets = collect_rbac_cleanup_protection_snapshot(
        db,
        batch_size=batch_size,
    )

    candidates = find_orphaned_rbac(
        repository_root=repository_root,
        valid_targets=valid_targets,
    )

    return RBACCleanupDryRunResult(
        valid_target_count=len(valid_targets),
        orphaned_candidates=tuple(candidates),
    )
