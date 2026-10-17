import re
from pathlib import Path
from uuid import UUID

from afterpush_api.services.argocd_observer_rbac import (
    render_argocd_application_rbac,
)
from afterpush_api.services.kubernetes_observer_rbac import (
    render_project_deployment_rbac,
)


APPLICATION_NAME_PATTERN = re.compile(
    r"^[a-z0-9]+(?:-[a-z0-9]+)*$"
)

VALID_ENVIRONMENTS = {"dev", "staging", "prod"}


def prepare_gitops_rbac(
    *,
    repository_root: Path,
    project_id: UUID,
    application_name: str,
    environment: str,
) -> tuple[Path, Path]:
    """
    Generate project-scoped observer RBAC in a GitOps checkout.

    Returns the ArgoCD and Deployment RBAC file paths.
    Does not commit, push or apply Kubernetes resources.
    """

    if environment not in VALID_ENVIRONMENTS:
        raise ValueError("Invalid RBAC environment.")

    if not APPLICATION_NAME_PATTERN.fullmatch(application_name):
        raise ValueError("Invalid RBAC application name.")

    if not isinstance(project_id, UUID):
        raise TypeError("project_id must be a UUID.")

    repository_root = Path(repository_root).resolve()

    if not repository_root.is_dir():
        raise ValueError("GitOps repository directory does not exist.")

    directory = (
        repository_root
        / "gitops"
        / "platform"
        / "rbac"
        / "projects"
        / environment
        / str(project_id)
        / application_name
    )

    argocd_yaml = render_argocd_application_rbac(
        project_id=project_id,
        application_name=application_name,
        environment=environment,
    )

    deployment_yaml = render_project_deployment_rbac(
        project_id=project_id,
        application_name=application_name,
        environment=environment,
    )

    directory.mkdir(parents=True, exist_ok=True)

    argocd_path = directory / "argocd-rbac.yaml"
    deployment_path = directory / "deployment-rbac.yaml"

    argocd_path.write_text(argocd_yaml, encoding="utf-8")
    deployment_path.write_text(deployment_yaml, encoding="utf-8")

    return argocd_path, deployment_path
