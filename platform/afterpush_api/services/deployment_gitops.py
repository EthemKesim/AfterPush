from dataclasses import dataclass
from pathlib import Path
from uuid import UUID

import yaml

from afterpush_api.services.gitops import (
    GitOpsError,
    get_values_path,
    write_gitops_values,
)
from afterpush_api.services.gitops_revision import (
    apply_deployment_revision,
)
from afterpush_api.services.sync import (
    sync_gitops_application,
)


class ConflictingGitOpsRevisionError(GitOpsError):
    """The same revision already exists with different deployment values."""


@dataclass(frozen=True)
class DeploymentGitOpsSpec:
    application_name: str
    environment: str
    image_repository: str
    image_tag: str
    port: int
    replicas: int
    project_id: UUID
    revision: int = 1


def prepare_deployment_gitops(
    repository_root: Path,
    spec: DeploymentGitOpsSpec,
) -> Path:
    """
    Prepare GitOps values while enforcing revision ordering.

    An existing revision cannot be reused with different
    image or application runtime settings.
    """

    gitops_root = repository_root / "gitops"

    values_path = get_values_path(
        gitops_root=gitops_root,
        application_name=spec.application_name,
        environment=spec.environment,
        project_id=spec.project_id,
    )

    if values_path.is_file():
        with values_path.open("r", encoding="utf-8") as file:
            current_values = yaml.safe_load(file)

        if not isinstance(current_values, dict):
            raise GitOpsError("Helm values must contain a YAML mapping.")

        apply_deployment_revision(
            current_values,
            revision=spec.revision,
        )

        current_revision = current_values.get(
            "deployment", {}
        ).get("revision", 0)

        if current_revision == spec.revision:
            image = current_values.get("image", {})
            service = current_values.get("service", {})

            same_configuration = (
                isinstance(image, dict)
                and isinstance(service, dict)
                and image.get("repository") == spec.image_repository
                and image.get("tag") == spec.image_tag
                and service.get("targetPort") == spec.port
                and (
                    current_values.get("replicaCount") == spec.replicas
                    or current_values.get("autoscaling", {}).get("enabled") is True
                )
            )

            if not same_configuration:
                raise ConflictingGitOpsRevisionError(
                    f"Revision {spec.revision} already exists "
                    "with different deployment configuration."
                )

            return values_path

    synced_path = sync_gitops_application(
        gitops_root=gitops_root,
        application_name=spec.application_name,
        environment=spec.environment,
        image_repository=spec.image_repository,
        image_tag=spec.image_tag,
        port=spec.port,
        replicas=spec.replicas,
        project_id=spec.project_id,
    )

    with synced_path.open("r", encoding="utf-8") as file:
        updated_values = yaml.safe_load(file)

    revisioned_values = apply_deployment_revision(
        updated_values,
        revision=spec.revision,
    )

    return write_gitops_values(
        gitops_root=gitops_root,
        application_name=spec.application_name,
        environment=spec.environment,
        values=revisioned_values,
        project_id=spec.project_id,
    )
