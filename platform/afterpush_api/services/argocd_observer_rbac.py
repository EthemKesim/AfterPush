from uuid import UUID

import yaml

from afterpush_api.services.argocd_identity import (
    build_argocd_application_identity,
)


def render_argocd_application_rbac(
    *,
    project_id: UUID,
    application_name: str,
    environment: str,
) -> str:
    """
    Render read-only RBAC for one ArgoCD Application.

    This function does not contact Kubernetes.
    """
    identity = build_argocd_application_identity(
        project_id=project_id,
        application_name=application_name,
        environment=environment,
    )

    role_name = f"{identity.application_name}-reader"

    role = {
        "apiVersion": "rbac.authorization.k8s.io/v1",
        "kind": "Role",
        "metadata": {
            "name": role_name,
            "namespace": "argocd",
        },
        "rules": [
            {
                "apiGroups": ["argoproj.io"],
                "resources": ["applications"],
                "resourceNames": [identity.application_name],
                "verbs": ["get"],
            }
        ],
    }

    binding = {
        "apiVersion": "rbac.authorization.k8s.io/v1",
        "kind": "RoleBinding",
        "metadata": {
            "name": f"{role_name}-binding",
            "namespace": "argocd",
        },
        "subjects": [
            {
                "kind": "ServiceAccount",
                "name": "afterpush-runtime-worker",
                "namespace": "afterpush-system",
            }
        ],
        "roleRef": {
            "kind": "Role",
            "name": role_name,
            "apiGroup": "rbac.authorization.k8s.io",
        },
    }

    return yaml.safe_dump_all(
        [role, binding],
        sort_keys=False,
    )
