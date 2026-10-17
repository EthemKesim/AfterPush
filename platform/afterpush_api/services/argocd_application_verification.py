from dataclasses import dataclass
from typing import Any

from afterpush_api.services.argocd_identity import (
    ArgoCDApplicationIdentity,
)


@dataclass(frozen=True)
class ArgoCDApplicationVerification:
    verified: bool
    reason: str


def verify_argocd_application(
    application: dict[str, Any],
    identity: ArgoCDApplicationIdentity,
    repository_url: str,
) -> ArgoCDApplicationVerification:
    """
    Verify that an ArgoCD Application targets the expected
    AfterPush deployment and GitOps configuration.

    This does not verify sync success or Kubernetes health.
    """

    if not isinstance(repository_url, str) or not repository_url.strip():
        raise ValueError("Invalid GitOps repository URL")

    if not isinstance(application, dict):
        return ArgoCDApplicationVerification(False, "invalid_application")

    metadata = application.get("metadata")
    spec = application.get("spec")

    if not isinstance(metadata, dict) or not isinstance(spec, dict):
        return ArgoCDApplicationVerification(False, "invalid_structure")

    if metadata.get("name") != identity.application_name:
        return ArgoCDApplicationVerification(False, "application_name_mismatch")

    if metadata.get("namespace") != "argocd":
        return ArgoCDApplicationVerification(False, "application_namespace_mismatch")

    destination = spec.get("destination")

    if not isinstance(destination, dict):
        return ArgoCDApplicationVerification(False, "missing_destination")

    if destination.get("namespace") != identity.namespace:
        return ArgoCDApplicationVerification(False, "destination_namespace_mismatch")

    if destination.get("server") != "https://kubernetes.default.svc":
        return ArgoCDApplicationVerification(False, "destination_server_mismatch")

    sources = spec.get("sources")

    if not isinstance(sources, list) or len(sources) != 2:
        return ArgoCDApplicationVerification(False, "invalid_sources")

    chart_source, values_source = sources

    if not isinstance(chart_source, dict) or not isinstance(values_source, dict):
        return ArgoCDApplicationVerification(False, "invalid_source_structure")

    for source in sources:
        if source.get("repoURL") != repository_url:
            return ArgoCDApplicationVerification(False, "repository_mismatch")

        if source.get("targetRevision") != "main":
            return ArgoCDApplicationVerification(False, "branch_mismatch")

    if chart_source.get("path") != "helm/afterpush":
        return ArgoCDApplicationVerification(False, "chart_path_mismatch")

    helm = chart_source.get("helm")

    if not isinstance(helm, dict):
        return ArgoCDApplicationVerification(False, "missing_helm_config")

    expected_values_file = f"$values/{identity.gitops_path}/values.yaml"

    if helm.get("valueFiles") != [expected_values_file]:
        return ArgoCDApplicationVerification(False, "values_path_mismatch")

    if values_source.get("ref") != "values":
        return ArgoCDApplicationVerification(False, "values_reference_mismatch")

    if "path" in values_source or "chart" in values_source:
        return ArgoCDApplicationVerification(False, "unexpected_values_source")

    if "ref" in chart_source or "chart" in chart_source:
        return ArgoCDApplicationVerification(False, "unexpected_chart_source")

    if spec.get("project") != "default":
        return ArgoCDApplicationVerification(False, "project_mismatch")

    return ArgoCDApplicationVerification(True, "verified")
