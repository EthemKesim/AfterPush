from pathlib import Path
from uuid import UUID

import yaml

from afterpush_api.services.argocd_identity import (
    build_argocd_application_identity,
)
from afterpush_api.services.bootstrap import build_resource_name


class GitOpsRBACValidationError(ValueError):
    """Generated RBAC does not match the allowed permissions."""


def _load_manifests(path: Path) -> list[dict]:
    try:
        documents = list(
            yaml.safe_load_all(path.read_text(encoding="utf-8"))
        )
    except (OSError, yaml.YAMLError) as exc:
        raise GitOpsRBACValidationError(
            f"Cannot read RBAC manifests: {path.name}"
        ) from exc

    if len(documents) != 2 or not all(
        isinstance(document, dict) for document in documents
    ):
        raise GitOpsRBACValidationError(
            f"Expected exactly two RBAC documents: {path.name}"
        )

    return documents


def _expected_role(
    *,
    name: str,
    namespace: str,
    api_group: str,
    resource: str,
    resource_name: str,
) -> dict:
    return {
        "apiVersion": "rbac.authorization.k8s.io/v1",
        "kind": "Role",
        "metadata": {
            "name": name,
            "namespace": namespace,
        },
        "rules": [
            {
                "apiGroups": [api_group],
                "resources": [resource],
                "resourceNames": [resource_name],
                "verbs": ["get"],
            }
        ],
    }


def _expected_binding(
    *,
    name: str,
    namespace: str,
) -> dict:
    return {
        "apiVersion": "rbac.authorization.k8s.io/v1",
        "kind": "RoleBinding",
        "metadata": {
            "name": f"{name}-binding",
            "namespace": namespace,
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
            "name": name,
            "apiGroup": "rbac.authorization.k8s.io",
        },
    }


def validate_gitops_rbac(
    *,
    rbac_paths: tuple[Path, Path],
    project_id: UUID,
    application_name: str,
    environment: str,
) -> None:
    """
    Verify exact RBAC permissions before GitOps publication.

    Rejects unexpected documents, fields, resources, and verbs.
    Does not contact Kubernetes.
    """
    if len(rbac_paths) != 2:
        raise GitOpsRBACValidationError(
            "Exactly two RBAC files are required"
        )

    identity = build_argocd_application_identity(
        project_id=project_id,
        application_name=application_name,
        environment=environment,
    )

    deployment_name = build_resource_name(
        application_name,
        project_id,
    )

    expected = {
        "argocd-rbac.yaml": [
            _expected_role(
                name=f"{identity.application_name}-reader",
                namespace="argocd",
                api_group="argoproj.io",
                resource="applications",
                resource_name=identity.application_name,
            ),
            _expected_binding(
                name=f"{identity.application_name}-reader",
                namespace="argocd",
            ),
        ],
        "deployment-rbac.yaml": [
            _expected_role(
                name=f"{identity.application_name}-deployment-reader",
                namespace=identity.namespace,
                api_group="apps",
                resource="deployments",
                resource_name=deployment_name,
            ),
            _expected_binding(
                name=f"{identity.application_name}-deployment-reader",
                namespace=identity.namespace,
            ),
        ],
    }

    actual_names = [Path(path).name for path in rbac_paths]

    if set(actual_names) != set(expected):
        raise GitOpsRBACValidationError(
            "Unexpected RBAC filenames"
        )

    for path in rbac_paths:
        path = Path(path)
        actual = _load_manifests(path)

        if actual != expected[path.name]:
            raise GitOpsRBACValidationError(
                f"Unexpected RBAC permissions in {path.name}"
            )
