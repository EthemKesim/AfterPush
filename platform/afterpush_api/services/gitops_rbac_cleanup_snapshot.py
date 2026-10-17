from sqlalchemy import text
from sqlalchemy.orm import Session

from afterpush_api.services.gitops_rbac_cleanup_protection import (
    collect_all_rbac_cleanup_protected_targets,
)

from afterpush_api.services.gitops_rbac_selection import (
    RBACPublicationTarget,
    collect_all_rbac_publication_targets,
)


def collect_rbac_targets_snapshot(
    db: Session,
    batch_size: int = 100,
) -> set[RBACPublicationTarget]:
    """
    Read all published RBAC targets from a consistent
    PostgreSQL REPEATABLE READ snapshot.

    Requires a fresh Session without an active transaction.
    Does not modify database records.
    """
    if batch_size < 1:
        raise ValueError("batch_size must be greater than zero")

    if db.in_transaction():
        raise ValueError(
            "RBAC snapshot requires a fresh database session"
        )

    with db.begin():
        db.execute(
            text(
                "SET TRANSACTION ISOLATION LEVEL "
                "REPEATABLE READ, READ ONLY"
            )
        )

        targets = collect_all_rbac_publication_targets(
            db,
            batch_size=batch_size,
        )

    return targets


def collect_rbac_cleanup_protection_snapshot(
    db: Session,
    batch_size: int = 100,
) -> set[RBACPublicationTarget]:
    """
    Collect cleanup-protected targets from one consistent
    PostgreSQL REPEATABLE READ, READ ONLY transaction.

    Includes pending, publishing and published deployments.
    """
    if batch_size < 1:
        raise ValueError("batch_size must be greater than zero")

    if db.in_transaction():
        raise ValueError(
            "RBAC snapshot requires a fresh database session"
        )

    with db.begin():
        db.execute(
            text(
                "SET TRANSACTION ISOLATION LEVEL "
                "REPEATABLE READ, READ ONLY"
            )
        )

        targets = collect_all_rbac_cleanup_protected_targets(
            db,
            batch_size=batch_size,
        )

    return targets
