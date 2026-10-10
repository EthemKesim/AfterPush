
from sqlalchemy.orm import Session

from afterpush_api.models import Deployment


def has_newer_deployment(
    db: Session,
    deployment: Deployment,
) -> bool:
    """
    Check whether a newer deployment exists for
    the same application and environment.

    Deployment ordering is based on revision numbers,
    not timestamps or UUIDs.
    """

    newer_deployment = (
        db.query(Deployment.id)
        .filter(
            Deployment.application_id == deployment.application_id,
            Deployment.environment == deployment.environment,
            Deployment.revision > deployment.revision,
        )
        .first()
    )

    return newer_deployment is not None
