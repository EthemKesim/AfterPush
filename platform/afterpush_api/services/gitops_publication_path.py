"""Validate GitOps publication paths before staging files."""

from pathlib import Path
from uuid import UUID

from afterpush_api.services.argocd_identity import (
    APPLICATION_NAME_PATTERN,
)


class GitOpsPublicationPathError(ValueError):
    """Raised when a GitOps publication path is not permitted."""


ALLOWED_ENVIRONMENTS = frozenset(
    {"dev", "staging", "prod"}
)


def validate_gitops_publication_path(
    relative_path: Path,
) -> str:
    """
    Validate an approved GitOps publication path.

    Returns:
        "deployment" or "namespace-bootstrap".
    """

    path = Path(relative_path)

    if path.is_absolute():
        raise GitOpsPublicationPathError(
            "Absolute publication paths are not allowed."
        )

    parts = path.parts

    if ".." in parts or "." in parts:
        raise GitOpsPublicationPathError(
            "Path traversal is not allowed."
        )

    if len(parts) != 6:
        raise GitOpsPublicationPathError(
            "Unexpected GitOps publication path structure."
        )

    if parts[:2] == ("gitops", "apps"):
        environment = parts[2]
        project_id = parts[3]
        application_name = parts[4]

        if parts[5] != "values.yaml":
            raise GitOpsPublicationPathError(
                "Deployment publication requires values.yaml."
            )

        publication_type = "deployment"

    elif parts[:3] == ("gitops", "platform", "namespaces"):
        environment = parts[3]
        project_id = parts[4]

        if parts[5] != "namespace.yaml":
            raise GitOpsPublicationPathError(
                "Bootstrap publication requires namespace.yaml."
            )

        application_name = None
        publication_type = "namespace-bootstrap"

    else:
        raise GitOpsPublicationPathError(
            "GitOps publication directory is not permitted."
        )

    if environment not in ALLOWED_ENVIRONMENTS:
        raise GitOpsPublicationPathError(
            "Unsupported deployment environment."
        )

    try:
        parsed_project_id = UUID(project_id)
    except (ValueError, AttributeError) as exc:
        raise GitOpsPublicationPathError(
            "Project identifier must be a valid UUID."
        ) from exc

    if str(parsed_project_id) != project_id:
        raise GitOpsPublicationPathError(
            "Project UUID must use canonical lowercase format."
        )

    if application_name is not None:
        if not (
            3 <= len(application_name) <= 100
            and APPLICATION_NAME_PATTERN.fullmatch(application_name)
        ):
            raise GitOpsPublicationPathError(
                "Invalid application name in GitOps path."
            )

    return publication_type
