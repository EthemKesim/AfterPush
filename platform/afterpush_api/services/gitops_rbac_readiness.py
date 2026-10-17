"""Verify that project-scoped observer RBAC is active in Kubernetes."""

from uuid import UUID

import yaml

from afterpush_api.services.argocd_observer_rbac import (
    render_argocd_application_rbac,
)
from afterpush_api.services.kubernetes_observer_rbac import (
    render_project_deployment_rbac,
)


class GitOpsRBACNotReady(RuntimeError):
    """Expected Kubernetes RBAC is missing or does not match policy."""


def _actual_role(role) -> dict:
    return {
        "apiVersion": "rbac.authorization.k8s.io/v1",
        "kind": "Role",
        "metadata": {
            "name": role.metadata.name,
            "namespace": role.metadata.namespace,
        },
        "rules": [
            {
                "apiGroups": list(rule.api_groups or []),
                "resources": list(rule.resources or []),
                "resourceNames": list(rule.resource_names or []),
                "verbs": list(rule.verbs or []),
            }
            for rule in (role.rules or [])
        ],
    }


def _actual_binding(binding) -> dict:
    return {
        "apiVersion": "rbac.authorization.k8s.io/v1",
        "kind": "RoleBinding",
        "metadata": {
            "name": binding.metadata.name,
            "namespace": binding.metadata.namespace,
        },
        "subjects": [
            {
                "kind": subject.kind,
                "name": subject.name,
                "namespace": subject.namespace,
            }
            for subject in (binding.subjects or [])
        ],
        "roleRef": {
            "kind": binding.role_ref.kind,
            "name": binding.role_ref.name,
            "apiGroup": binding.role_ref.api_group,
        },
    }


def verify_gitops_rbac(
    *,
    rbac_api,
    project_id: UUID,
    application_name: str,
    environment: str,
) -> None:
    """Fail closed unless both scoped Role/RoleBinding pairs match policy."""

    if rbac_api is None:
        raise GitOpsRBACNotReady("Kubernetes RbacAuthorizationV1Api is missing.")

    expected_sets = (
        render_argocd_application_rbac(
            project_id=project_id,
            application_name=application_name,
            environment=environment,
        ),
        render_project_deployment_rbac(
            project_id=project_id,
            application_name=application_name,
            environment=environment,
        ),
    )

    for manifest_yaml in expected_sets:
        documents = list(yaml.safe_load_all(manifest_yaml))

        if len(documents) != 2:
            raise GitOpsRBACNotReady("Invalid expected RBAC document count.")

        expected_role, expected_binding = documents

        role_namespace = expected_role["metadata"]["namespace"]
        role_name = expected_role["metadata"]["name"]

        binding_namespace = expected_binding["metadata"]["namespace"]
        binding_name = expected_binding["metadata"]["name"]

        try:
            role = rbac_api.read_namespaced_role(
                role_name,
                role_namespace,
            )
            binding = rbac_api.read_namespaced_role_binding(
                binding_name,
                binding_namespace,
            )
        except Exception as exc:
            raise GitOpsRBACNotReady(
                f"RBAC resources unavailable: {role_namespace}/{role_name}"
            ) from exc

        if _actual_role(role) != expected_role:
            raise GitOpsRBACNotReady(
                f"RBAC Role policy mismatch: {role_namespace}/{role_name}"
            )

        if _actual_binding(binding) != expected_binding:
            raise GitOpsRBACNotReady(
                f"RBAC RoleBinding policy mismatch: "
                f"{binding_namespace}/{binding_name}"
            )
