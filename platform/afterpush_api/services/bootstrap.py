
from pathlib import Path
from uuid import UUID

import yaml

from afterpush_api.services.gitops import (
    GitOpsError,
    get_values_path,
)


class GitOpsBootstrapError(GitOpsError):
    """Raised when a GitOps application cannot be initialized."""


def build_initial_values(
    application_name: str,
    image_repository: str,
    image_tag: str,
    port: int,
    replicas: int,
    environment: str,
) -> dict:
    """
    Build initial Helm values for an application.
    """

    if not 1 <= port <= 65535:
        raise GitOpsBootstrapError(
            "Application port must be between 1 and 65535."
        )

    if replicas < 1:
        raise GitOpsBootstrapError(
            "Application replicas must be at least 1."
        )

    return {
        "application": {
            "name": application_name,
        },
        "environment": {
            "name": environment,
        },
        "replicaCount": replicas,
        "image": {
            "repository": image_repository,
            "tag": image_tag,
            "pullPolicy": "IfNotPresent",
        },
        "service": {
            "type": "ClusterIP",
            "port": 80,
            "targetPort": port,
        },
        "config": {
            "appEnv": environment,
            "logLevel": "info",
        },
        "secret": {
            "enabled": False,
            "name": "",
        },
        "ingress": {
            "enabled": False,
            "className": "nginx",
            "annotations": {},
            "host": "",
            "path": "/",
            "pathType": "Prefix",
        },
        "autoscaling": {
            "enabled": False,
            "minReplicas": replicas,
            "maxReplicas": max(replicas, 2),
            "targetCPUUtilizationPercentage": 50,
        },
        "resources": {
            "requests": {
                "cpu": "100m",
                "memory": "128Mi",
            },
            "limits": {
                "cpu": "500m",
                "memory": "256Mi",
            },
        },
        "probes": {
            "readiness": {
                "path": "/health",
                "initialDelaySeconds": 2,
                "periodSeconds": 5,
            },
            "liveness": {
                "path": "/health",
                "initialDelaySeconds": 5,
                "periodSeconds": 10,
            },
        },
        "monitoring": {
            "enabled": False,
        },
    }


def bootstrap_gitops_application(
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
    Create initial GitOps values for a new application.

    When project_id is supplied, the values file is stored
    under the project's UUID directory.

    Existing values files are never overwritten.
    """

    values_path = get_values_path(
        gitops_root,
        application_name,
        environment,
        project_id=project_id,
    )

    values = build_initial_values(
        application_name=application_name,
        image_repository=image_repository,
        image_tag=image_tag,
        port=port,
        replicas=replicas,
        environment=environment,
    )

    values_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    try:
        with values_path.open(
            "x",
            encoding="utf-8",
        ) as file:
            yaml.safe_dump(
                values,
                file,
                sort_keys=False,
            )
    except FileExistsError as exc:
        raise GitOpsBootstrapError(
            f"GitOps application already exists: {values_path}"
        ) from exc

    return values_path
