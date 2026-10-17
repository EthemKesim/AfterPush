from pathlib import Path
from uuid import UUID

import yaml

from afterpush_api.services.argocd_identity import (
    build_argocd_application_identity,
)
from afterpush_api.services.bootstrap import build_resource_name


RBAC_TEMPLATE = (
    Path(__file__).resolve().parents[3]
    / "k8s"
    / "observer"
    / "project-deployment-reader-rbac.yaml"
)


def render_project_deployment_rbac(
    *,
    project_id: UUID,
    application_name: str,
    environment: str,
) -> str:
    """
    Render read-only RBAC restricted to one Deployment.

    Does not connect to Kubernetes or apply resources.
    """
    identity = build_argocd_application_identity(
        project_id=project_id,
        application_name=application_name,
        environment=environment,
    )

    deployment_name = build_resource_name(
        application_name,
        project_id,
    )

    manifests = list(
        yaml.safe_load_all(RBAC_TEMPLATE.read_text())
    )

    role_name = f"{identity.application_name}-deployment-reader"

    for manifest in manifests:
        manifest["metadata"]["namespace"] = identity.namespace

        if manifest["kind"] == "Role":
            manifest["metadata"]["name"] = role_name
            manifest["rules"][0]["resourceNames"] = [
                deployment_name
            ]

        elif manifest["kind"] == "RoleBinding":
            manifest["metadata"]["name"] = f"{role_name}-binding"
            manifest["roleRef"]["name"] = role_name

    return yaml.safe_dump_all(
        manifests,
        sort_keys=False,
    )
