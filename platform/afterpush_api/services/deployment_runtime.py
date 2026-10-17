from dataclasses import dataclass
from typing import Literal

from afterpush_api.services.argocd_observation import (
    ArgoCDObservation,
)
from afterpush_api.services.kubernetes_rollout import (
    KubernetesRolloutObservation,
)


RuntimeStatus = Literal[
    "healthy",
    "progressing",
    "degraded",
    "out_of_sync",
    "revision_mismatch",
    "unverified",
]


@dataclass(frozen=True)
class DeploymentRuntimeStatus:
    status: RuntimeStatus
    rollout_complete: bool
    revision_verified: bool


def evaluate_deployment_runtime(
    argocd: ArgoCDObservation,
    kubernetes: KubernetesRolloutObservation,
    *,
    expected_revision: int,
    gitops_revision_verified: bool = False,
) -> DeploymentRuntimeStatus:
    """
    Combine ArgoCD and Kubernetes observations.

    GitOps verification must be established independently.
    A missing Kubernetes revision cannot establish rollout progress.
    """

    if type(expected_revision) is not int or expected_revision < 1:
        raise ValueError("Invalid expected revision")

    if not isinstance(gitops_revision_verified, bool):
        raise ValueError("Invalid GitOps verification result")

    observed_revision = kubernetes.observed_revision

    if observed_revision is None:
        status: RuntimeStatus = "unverified"

    elif observed_revision != expected_revision:
        status = "revision_mismatch"

    elif not gitops_revision_verified:
        status = "unverified"

    elif argocd.sync_status == "OutOfSync":
        status = "out_of_sync"

    elif argocd.sync_status != "Synced":
        status = "unverified"

    elif argocd.health_status == "Degraded":
        status = "degraded"

    elif not kubernetes.rollout_complete:
        status = "progressing"

    elif argocd.health_status == "Healthy":
        status = "healthy"

    else:
        status = "progressing"

    return DeploymentRuntimeStatus(
        status=status,
        rollout_complete=kubernetes.rollout_complete,
        revision_verified=(
            gitops_revision_verified
            and observed_revision == expected_revision
        ),
    )
