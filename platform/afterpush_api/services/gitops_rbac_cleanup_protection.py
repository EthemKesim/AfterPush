from sqlalchemy import select, tuple_
from sqlalchemy.orm import Session

from afterpush_api.models import Application, Deployment
from afterpush_api.services.gitops_rbac_selection import (
    RBACPublicationTarget,
)


def get_rbac_cleanup_protected_targets(
    db: Session,
    limit: int = 100,
    after: RBACPublicationTarget | None = None,
) -> list[RBACPublicationTarget]:
    """
    Return application/environment targets with deployment history.

    Unlike RBAC publication selection, cleanup protection includes
    pending, publishing and published deployments.

    Read-only; does not delete or modify resources.
    """
    if limit < 1:
        raise ValueError("limit must be greater than zero")

    if after is not None and not isinstance(
        after, RBACPublicationTarget
    ):
        raise TypeError("after must be an RBACPublicationTarget")

    columns = (
        Application.project_id,
        Application.name,
        Deployment.environment,
    )

    statement = (
        select(*columns)
        .join(
            Deployment,
            Deployment.application_id == Application.id,
        )
        .where(
            Deployment.status.in_(
                ("pending", "publishing", "published")
            )
        )
        .distinct()
    )

    if after is not None:
        statement = statement.where(
            tuple_(*columns)
            > tuple_(
                after.project_id,
                after.application_name,
                after.environment,
            )
        )

    statement = statement.order_by(*columns).limit(limit)

    return [
        RBACPublicationTarget(
            project_id=project_id,
            application_name=application_name,
            environment=environment,
        )
        for project_id, application_name, environment in (
            db.execute(statement).all()
        )
    ]


def collect_all_rbac_cleanup_protected_targets(
    db: Session,
    batch_size: int = 100,
) -> set[RBACPublicationTarget]:
    """
    Collect all cleanup-protected targets with keyset pagination.

    Query failures propagate instead of returning incomplete results.
    """
    if batch_size < 1:
        raise ValueError("batch_size must be greater than zero")

    collected: set[RBACPublicationTarget] = set()
    cursor: RBACPublicationTarget | None = None

    while True:
        page = get_rbac_cleanup_protected_targets(
            db,
            limit=batch_size,
            after=cursor,
        )

        if not page:
            return collected

        collected.update(page)
        cursor = page[-1]
