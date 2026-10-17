
import hashlib
import re
from pathlib import Path
from uuid import UUID

import yaml

from afterpush_api.services.gitops import (
    GitOpsError,
    get_values_path,
)


class GitOpsBootstrapError(GitOpsError):
    """Raised when a GitOps application cannot be initialized."""


MAX_RESOURCE_NAME_LENGTH = 45
RESOURCE_HASH_LENGTH = 12


def build_resource_name(
    application_name: str,
    project_id: UUID,
) -> str:
    """
    Build a stable, project-aware Kubernetes resource name.

    The hash includes both the project UUID and the complete
    application name to distinguish applications within a project.
    """

    if not application_name:
        raise GitOpsBootstrapError(
            "Application name cannot be empty."
        )

    normalized_name = re.sub(
        r"[^a-z0-9-]+",
        "-",
        application_name.lower(),
    ).strip("-")

    if not normalized_name:
        raise GitOpsBootstrapError(
            "Application name cannot produce a valid Kubernetes resource name."
        )

    identity = f"{project_id}:{application_name}"

    identity_hash = hashlib.sha256(
        identity.encode("utf-8")
    ).hexdigest()[:RESOURCE_HASH_LENGTH]

    available_prefix_length = (
        MAX_RESOURCE_NAME_LENGTH - RESOURCE_HASH_LENGTH - 1
    )

    prefix = normalized_name[:available_prefix_length].rstrip("-")

    if not prefix:
        raise GitOpsBootstrapError(
            "Application name cannot produce a valid Kubernetes resource name."
        )

    return f"{prefix}-{identity_hash}"


def build_initial_values(
    application_name: str,
    image_repository: str,
    image_tag: str,
    port: int,
    replicas: int,
    environment: str,
    project_id: UUID | None = None,
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

    application_values = {
        "name": application_name,
    }

    if project_id is not None:
        application_values["resourceName"] = build_resource_name(
            application_name,
            project_id,
        )

    return {
        "application": application_values,
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

    Project-aware applications receive a stable Kubernetes
    resource name based on their project UUID and app name.

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
        project_id=project_id,
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
