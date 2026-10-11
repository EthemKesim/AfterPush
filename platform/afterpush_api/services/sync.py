
from pathlib import Path
from uuid import UUID

from afterpush_api.services.bootstrap import (
    bootstrap_gitops_application,
)
from afterpush_api.services.gitops import (
    get_values_path,
    prepare_gitops_values,
    write_gitops_values,
)
from afterpush_api.services.locking import (
    gitops_application_lock,
)


def sync_gitops_application(
    gitops_root: Path,
    application_name: str,
    environment: str,
    image_repository: str,
    image_tag: str,
    port: int,
    replicas: int,
    project_id: UUID | None = None,
) -> Path:
    """
    Create or update an application's GitOps configuration.

    When project_id is supplied, the GitOps configuration
    and filesystem lock are isolated by project.

    A filesystem lock serializes cooperating processes
    modifying the same application/environment.

    Bootstrap:
        Creates values.yaml when the application is new.

    Update:
        Updates image repository and tag while preserving
        existing Helm configuration.
    """

    with gitops_application_lock(
        gitops_root=gitops_root,
        application_name=application_name,
        environment=environment,
        project_id=project_id,
    ):
        values_path = get_values_path(
            gitops_root=gitops_root,
            application_name=application_name,
            environment=environment,
            project_id=project_id,
        )

        if not values_path.exists():
            return bootstrap_gitops_application(
                gitops_root=gitops_root,
                application_name=application_name,
                environment=environment,
                image_repository=image_repository,
                image_tag=image_tag,
                port=port,
                replicas=replicas,
                project_id=project_id,
            )

        updated_values = prepare_gitops_values(
            gitops_root=gitops_root,
            application_name=application_name,
            environment=environment,
            image_repository=image_repository,
            image_tag=image_tag,
            project_id=project_id,
        )

        return write_gitops_values(
            gitops_root=gitops_root,
            application_name=application_name,
            environment=environment,
            values=updated_values,
            project_id=project_id,
        )
