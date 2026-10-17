from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ArgoCDResourceVerification:
    verified: bool
    reason: str


def verify_argocd_deployment_resource(
    application: dict[str, Any],
    deployment: dict[str, Any],
    *,
    expected_name: str,
    expected_namespace: str,
) -> ArgoCDResourceVerification:
    """
    Verify that the supplied Deployment identity appears in
    the ArgoCD Application's resource inventory.

    This does not independently establish Kubernetes ownership
    or prove that the resource is currently healthy.
    """

    if not isinstance(expected_name, str) or not expected_name:
        raise ValueError("Invalid expected Deployment name")

    if not isinstance(expected_namespace, str) or not expected_namespace:
        raise ValueError("Invalid expected Deployment namespace")

    if not isinstance(application, dict) or not isinstance(deployment, dict):
        return ArgoCDResourceVerification(False, "invalid_snapshot")

    metadata = deployment.get("metadata")

    if not isinstance(metadata, dict):
        return ArgoCDResourceVerification(False, "invalid_deployment_metadata")

    if metadata.get("name") != expected_name:
        return ArgoCDResourceVerification(False, "deployment_name_mismatch")

    if metadata.get("namespace") != expected_namespace:
        return ArgoCDResourceVerification(False, "deployment_namespace_mismatch")

    if deployment.get("kind") != "Deployment":
        return ArgoCDResourceVerification(False, "invalid_deployment_kind")

    if deployment.get("apiVersion") != "apps/v1":
        return ArgoCDResourceVerification(False, "invalid_deployment_api_version")

    status = application.get("status")

    if not isinstance(status, dict):
        return ArgoCDResourceVerification(False, "missing_application_status")

    resources = status.get("resources")

    if not isinstance(resources, list):
        return ArgoCDResourceVerification(False, "missing_resource_inventory")

    for resource in resources:
        if not isinstance(resource, dict):
            continue

        if (
            resource.get("group") == "apps"
            and resource.get("version") == "v1"
            and resource.get("kind") == "Deployment"
            and resource.get("name") == expected_name
            and resource.get("namespace") == expected_namespace
        ):
            return ArgoCDResourceVerification(True, "verified")

    return ArgoCDResourceVerification(False, "deployment_not_managed")
