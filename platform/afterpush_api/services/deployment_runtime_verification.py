from dataclasses import dataclass
from typing import Any
from uuid import UUID

from afterpush_api.services.argocd_application_verification import (
    verify_argocd_application,
)
from afterpush_api.services.argocd_identity import (
    ArgoCDApplicationIdentity,
)
from afterpush_api.services.argocd_observation import (
    parse_argocd_observation,
)
from afterpush_api.services.argocd_resource_verification import (
    verify_argocd_deployment_resource,
)
from afterpush_api.services.argocd_sync_verification import (
    verify_argocd_sync,
)
from afterpush_api.services.bootstrap import (
    build_resource_name,
)
from afterpush_api.services.deployment_runtime import (
    DeploymentRuntimeStatus,
    evaluate_deployment_runtime,
)
from afterpush_api.services.kubernetes_rollout import (
    evaluate_kubernetes_rollout,
)


@dataclass(frozen=True)
class DeploymentRuntimeVerification:
    status: str
    reason: str
    rollout_complete: bool
    revision_verified: bool


def verify_deployment_runtime(
    *,
    application: dict[str, Any],
    deployment: dict[str, Any],
    identity: ArgoCDApplicationIdentity,
    repository_url: str,
    expected_commit_sha: str,
    expected_revision: int,
    project_id: UUID,
    application_name: str,
) -> DeploymentRuntimeVerification:
    """
    Evaluate supplied ArgoCD and Kubernetes snapshots.

    Verifies Application configuration, Deployment identity,
    ArgoCD resource inventory, GitOps sync, and rollout.

    Does not fetch live cluster state or establish snapshot freshness.
    """

    def unverified(reason: str) -> DeploymentRuntimeVerification:
        return DeploymentRuntimeVerification(
            status="unverified",
            reason=reason,
            rollout_complete=False,
            revision_verified=False,
        )

    application_result = verify_argocd_application(
        application,
        identity,
        repository_url,
    )

    if not application_result.verified:
        return unverified(application_result.reason)

    expected_deployment_name = build_resource_name(
        application_name,
        project_id,
    )

    resource_result = verify_argocd_deployment_resource(
        application,
        deployment,
        expected_name=expected_deployment_name,
        expected_namespace=identity.namespace,
    )

    if not resource_result.verified:
        return unverified(resource_result.reason)

    sync_result = verify_argocd_sync(
        application,
        expected_commit_sha,
    )

    if not sync_result.verified:
        return unverified(sync_result.reason)

    argocd_observation = parse_argocd_observation(application)

    kubernetes_observation = evaluate_kubernetes_rollout(
        deployment,
        expected_revision,
    )

    runtime: DeploymentRuntimeStatus = evaluate_deployment_runtime(
        argocd_observation,
        kubernetes_observation,
        expected_revision=expected_revision,
        gitops_revision_verified=True,
    )

    return DeploymentRuntimeVerification(
        status=runtime.status,
        reason=runtime.status,
        rollout_complete=runtime.rollout_complete,
        revision_verified=runtime.revision_verified,
    )
