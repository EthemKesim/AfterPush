"""Coordinate project RBAC readiness without publishing workloads."""

from dataclasses import dataclass
from typing import Callable, Literal
from uuid import UUID

from afterpush_api.services.gitops_rbac_publication import (
    publish_rbac_with_retry,
)
from afterpush_api.services.gitops_rbac_readiness import (
    GitOpsRBACNotReady,
    verify_gitops_rbac,
)


RBACBootstrapStatus = Literal["ready", "waiting"]


@dataclass(frozen=True)
class RBACBootstrapResult:
    status: RBACBootstrapStatus
    commit_sha: str | None


def reconcile_gitops_rbac(
    *,
    repository_url: str,
    project_id: UUID,
    application_name: str,
    environment: str,
    rbac_api,
    verifier: Callable = verify_gitops_rbac,
    publisher: Callable = publish_rbac_with_retry,
) -> RBACBootstrapResult:
    """
    Ensure project observer RBAC is requested before workload publication.

    Readiness is verified against Kubernetes, not inferred from a Git commit.
    This function does not publish workloads or update deployment state.
    """

    if not repository_url or not repository_url.strip():
        raise ValueError("GitOps repository URL cannot be empty.")

    if rbac_api is None:
        raise GitOpsRBACNotReady(
            "Kubernetes RbacAuthorizationV1Api is not configured."
        )

    try:
        verifier(
            rbac_api=rbac_api,
            project_id=project_id,
            application_name=application_name,
            environment=environment,
        )
    except GitOpsRBACNotReady:
        commit_sha = publisher(
            repository_url=repository_url,
            project_id=project_id,
            application_name=application_name,
            environment=environment,
        )

        if not commit_sha:
            raise RuntimeError(
                "RBAC publisher returned no commit SHA."
            )

        return RBACBootstrapResult(
            status="waiting",
            commit_sha=commit_sha,
        )

    return RBACBootstrapResult(
        status="ready",
        commit_sha=None,
    )
