from pathlib import Path
from uuid import UUID

from afterpush_api.services.namespace_bootstrap import (
    render_namespace_bootstrap,
)
from afterpush_api.services.namespace_bootstrap_validator import (
    validate_namespace_bootstrap,
)


def prepare_namespace_bootstrap(
    *,
    repository_root: Path,
    project_id: UUID,
    application_name: str,
    environment: str,
) -> Path:
    """
    Prepare validated namespace bootstrap manifests in a GitOps checkout.

    Does not commit, push, or apply Kubernetes resources.
    """
    if not isinstance(project_id, UUID):
        raise TypeError("project_id must be a UUID.")

    if environment not in {"dev", "staging", "prod"}:
        raise ValueError("Invalid bootstrap environment.")

    repository_root = Path(repository_root).resolve()

    if not repository_root.is_dir():
        raise ValueError("GitOps repository directory does not exist.")

    rendered = render_namespace_bootstrap(
        project_id=project_id,
        application_name=application_name,
        environment=environment,
    )

    validate_namespace_bootstrap(
        rendered_yaml=rendered,
        project_id=project_id,
        application_name=application_name,
        environment=environment,
    )

    directory = (
        repository_root
        / "gitops"
        / "platform"
        / "namespaces"
        / environment
        / str(project_id)
    )

    directory.mkdir(parents=True, exist_ok=True)

    target = directory / "namespace.yaml"

    if target.exists():
        existing = target.read_text(encoding="utf-8")
        if existing != rendered:
            raise ValueError(
                "Existing namespace bootstrap differs from expected policy."
            )
        return target

    target.write_text(rendered, encoding="utf-8")

    return target
