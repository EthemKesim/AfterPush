from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import select, tuple_
from sqlalchemy.orm import Session

from afterpush_api.models import Application, Deployment


@dataclass(frozen=True)
class RBACPublicationTarget:
    project_id: UUID
    application_name: str
    environment: str


def get_rbac_publication_targets(
    db: Session,
    limit: int = 20,
    after: RBACPublicationTarget | None = None,
) -> list[RBACPublicationTarget]:
    """
    Return distinct published application/environment targets.

    Supports keyset pagination through the 'after' cursor.
    Does not publish or modify resources.
    """
    if limit < 1:
        raise ValueError("limit must be greater than zero")

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
        .where(Deployment.status == "published")
        .distinct()
    )

    if after is not None:
        if not isinstance(after, RBACPublicationTarget):
            raise TypeError("after must be an RBACPublicationTarget")

        statement = statement.where(
            tuple_(*columns) > tuple_(
                after.project_id,
                after.application_name,
                after.environment,
            )
        )

    statement = (
        statement
        .order_by(*columns)
        .limit(limit)
    )

    rows = db.execute(statement).all()

    return [
        RBACPublicationTarget(
            project_id=project_id,
            application_name=application_name,
            environment=environment,
        )
        for project_id, application_name, environment in rows
    ]


def collect_all_rbac_publication_targets(
    db: Session,
    batch_size: int = 100,
) -> set[RBACPublicationTarget]:
    """
    Collect every published RBAC target using keyset pagination.

    Returns only after all database pages have been read.
    Raises on query errors; never returns a partial set.
    """
    if batch_size < 1:
        raise ValueError("batch_size must be greater than zero")

    collected: set[RBACPublicationTarget] = set()
    cursor: RBACPublicationTarget | None = None

    while True:
        page = get_rbac_publication_targets(
            db,
            limit=batch_size,
            after=cursor,
        )

        if not page:
            return collected

        collected.update(page)
        cursor = page[-1]
