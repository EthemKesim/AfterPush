from uuid import UUID

import yaml

from afterpush_api.services.namespace_bootstrap import (
    render_namespace_bootstrap,
)


class NamespaceBootstrapValidationError(ValueError):
    """Namespace bootstrap manifests violate the expected policy."""


def validate_namespace_bootstrap(
    *,
    rendered_yaml: str,
    project_id: UUID,
    application_name: str | None = None,
    environment: str = "dev",
) -> None:
    try:
        documents = list(yaml.safe_load_all(rendered_yaml))
    except yaml.YAMLError as exc:
        raise NamespaceBootstrapValidationError(
            "Invalid namespace bootstrap YAML."
        ) from exc

    if len(documents) != 3:
        raise NamespaceBootstrapValidationError(
            "Exactly three Kubernetes resources are required."
        )

    if not all(isinstance(document, dict) for document in documents):
        raise NamespaceBootstrapValidationError(
            "All Kubernetes resources must be mappings."
        )

    expected_yaml = render_namespace_bootstrap(
        project_id=project_id,
        application_name=application_name,
        environment=environment,
    )

    expected_documents = list(yaml.safe_load_all(expected_yaml))

    if documents != expected_documents:
        raise NamespaceBootstrapValidationError(
            "Namespace bootstrap manifests do not match the security policy."
        )
