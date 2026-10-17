from uuid import UUID

import yaml

from afterpush_api.services.argocd_identity import (
    build_project_namespace,
)


VALID_ENVIRONMENTS = {"dev", "staging", "prod"}


def render_namespace_bootstrap(
    *,
    project_id: UUID,
    application_name: str | None = None,
    environment: str = "dev",
) -> str:
    if not isinstance(project_id, UUID):
        raise TypeError("project_id must be a UUID.")

    if environment not in VALID_ENVIRONMENTS:
        raise ValueError("Invalid environment.")

    namespace = build_project_namespace(
        project_id=project_id,
        environment=environment,
    )

    manifests = [
        {
            "apiVersion": "v1",
            "kind": "Namespace",
            "metadata": {
                "name": namespace,
                "labels": {
                    "app.kubernetes.io/managed-by": "afterpush",
                    "afterpush.io/environment": environment,
                    "pod-security.kubernetes.io/enforce": "restricted",
                    "pod-security.kubernetes.io/enforce-version": "latest",
                    "pod-security.kubernetes.io/audit": "restricted",
                    "pod-security.kubernetes.io/warn": "restricted",
                },
            },
        },
        {
            "apiVersion": "v1",
            "kind": "ResourceQuota",
            "metadata": {
                "name": "afterpush-resource-quota",
                "namespace": namespace,
            },
            "spec": {
                "hard": {
                    "requests.cpu": "2",
                    "requests.memory": "4Gi",
                    "limits.cpu": "4",
                    "limits.memory": "8Gi",
                    "pods": "10",
                    "persistentvolumeclaims": "3",
                },
            },
        },
        {
            "apiVersion": "v1",
            "kind": "LimitRange",
            "metadata": {
                "name": "afterpush-container-limits",
                "namespace": namespace,
            },
            "spec": {
                "limits": [
                    {
                        "type": "Container",
                        "defaultRequest": {
                            "cpu": "100m",
                            "memory": "128Mi",
                        },
                        "default": {
                            "cpu": "500m",
                            "memory": "512Mi",
                        },
                        "max": {
                            "cpu": "2",
                            "memory": "2Gi",
                        },
                        "min": {
                            "cpu": "25m",
                            "memory": "32Mi",
                        },
                    }
                ],
            },
        },
    ]

    return yaml.safe_dump_all(
        manifests,
        sort_keys=False,
    )
