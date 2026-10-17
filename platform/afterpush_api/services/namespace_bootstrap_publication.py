"""Publish validated namespace bootstrap manifests to GitOps."""

from dataclasses import dataclass
from uuid import UUID

from afterpush_api.services.gitops_publish_coordinator import (
    publish_with_retry,
)
from afterpush_api.services.namespace_bootstrap_preparation import (
    prepare_namespace_bootstrap,
)

from afterpush_api.services.namespace_bootstrap_validator import (
    validate_namespace_bootstrap,
)


@dataclass(frozen=True)
class NamespaceBootstrapPublicationSpec:
    project_id: UUID
    application_name: str
    environment: str


def publish_namespace_bootstrap(
    *,
    repository_url: str,
    spec: NamespaceBootstrapPublicationSpec,
    max_attempts: int = 3,
) -> str:
    """
    Publish namespace bootstrap configuration to GitOps main.

    The operation is idempotent for an unchanged manifest.

    This function does not apply Kubernetes resources, verify
    live readiness, or publish application workloads.
    """
    if not repository_url or not repository_url.strip():
        raise ValueError("GitOps repository URL cannot be empty.")

    if not isinstance(spec, NamespaceBootstrapPublicationSpec):
        raise TypeError(
            "spec must be a NamespaceBootstrapPublicationSpec."
        )

    if not isinstance(spec.project_id, UUID):
        raise TypeError("project_id must be a UUID.")

    if spec.environment not in {"dev", "staging", "prod"}:
        raise ValueError("Invalid bootstrap environment.")

    def prepare_manifest(repository_root):
        return prepare_namespace_bootstrap(
            repository_root=repository_root,
            project_id=spec.project_id,
            application_name=spec.application_name,
            environment=spec.environment,
        )

    def validate_manifest(manifest_path):
        validate_namespace_bootstrap(
            rendered_yaml=manifest_path.read_text(encoding="utf-8"),
            project_id=spec.project_id,
            application_name=spec.application_name,
            environment=spec.environment,
        )

    return publish_with_retry(
        repository_url=repository_url,
        prepare_values=prepare_manifest,
        commit_message=(
            f"bootstrap({spec.environment}): "
            f"namespace for project {spec.project_id}"
        ),
        max_attempts=max_attempts,
        validate_content=validate_manifest,
    )
