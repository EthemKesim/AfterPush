import logging
from dataclasses import dataclass, field

from sqlalchemy.orm import Session

from afterpush_api.services.gitops_rbac_publication import (
    publish_rbac_with_retry,
)
from afterpush_api.services.gitops_rbac_selection import (
    RBACPublicationTarget,
    get_rbac_publication_targets,
)


logger = logging.getLogger(__name__)


@dataclass
class RBACReconciliationResult:
    processed: int = 0
    succeeded: int = 0
    failed: int = 0
    failed_targets: list[RBACPublicationTarget] = field(
        default_factory=list
    )


def reconcile_published_rbac(
    *,
    db: Session,
    repository_url: str,
    batch_size: int = 20,
) -> RBACReconciliationResult:
    """
    Reconcile observer RBAC for all published deployment targets.

    Processes targets in keyset-paginated batches.
    A publication failure does not stop other targets.

    Does not apply resources directly to Kubernetes.
    """

    if batch_size < 1:
        raise ValueError("batch_size must be greater than zero")

    result = RBACReconciliationResult()
    cursor = None

    while True:
        targets = get_rbac_publication_targets(
            db,
            limit=batch_size,
            after=cursor,
        )

        if not targets:
            break

        for target in targets:
            result.processed += 1

            try:
                publish_rbac_with_retry(
                    repository_url=repository_url,
                    project_id=target.project_id,
                    application_name=target.application_name,
                    environment=target.environment,
                )
            except Exception:
                result.failed += 1
                result.failed_targets.append(target)

                logger.exception(
                    "RBAC reconciliation failed for "
                    "project=%s application=%s environment=%s",
                    target.project_id,
                    target.application_name,
                    target.environment,
                )
            else:
                result.succeeded += 1

        cursor = targets[-1]

    return result
