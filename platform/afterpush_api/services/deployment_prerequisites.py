"""Coordinate namespace and RBAC prerequisites before deployment."""

from dataclasses import dataclass
from typing import Callable, Literal
from uuid import UUID

from afterpush_api.services.namespace_bootstrap_orchestrator import (
    reconcile_namespace_bootstrap,
)
from afterpush_api.services.namespace_bootstrap_publication import (
    NamespaceBootstrapPublicationSpec,
)
from afterpush_api.services.gitops_rbac_orchestrator import (
    reconcile_gitops_rbac,
)


PrerequisiteStatus = Literal["ready", "waiting"]


@dataclass(frozen=True)
class DeploymentPrerequisitesResult:
    status: PrerequisiteStatus
    stage: str | None
    commit_sha: str | None


def reconcile_deployment_prerequisites(
    *,
    repository_url: str,
    project_id: UUID,
    application_name: str,
    environment: str,
    core_api,
    rbac_api,
    namespace_reconciler: Callable = reconcile_namespace_bootstrap,
    rbac_reconciler: Callable = reconcile_gitops_rbac,
) -> DeploymentPrerequisitesResult:
    """
    Prepare namespace first, then RBAC.

    Does not publish workloads or modify deployment database state.
    A GitOps commit does not imply Kubernetes readiness.
    """

    namespace_result = namespace_reconciler(
        repository_url=repository_url,
        spec=NamespaceBootstrapPublicationSpec(
            project_id=project_id,
            application_name=application_name,
            environment=environment,
        ),
        core_api=core_api,
    )

    if namespace_result.status == "waiting":
        return DeploymentPrerequisitesResult(
            status="waiting",
            stage="namespace",
            commit_sha=namespace_result.commit_sha,
        )

    if namespace_result.status != "ready":
        raise RuntimeError("Unexpected namespace bootstrap status.")

    rbac_result = rbac_reconciler(
        repository_url=repository_url,
        project_id=project_id,
        application_name=application_name,
        environment=environment,
        rbac_api=rbac_api,
    )

    if rbac_result.status == "waiting":
        return DeploymentPrerequisitesResult(
            status="waiting",
            stage="rbac",
            commit_sha=rbac_result.commit_sha,
        )

    if rbac_result.status != "ready":
        raise RuntimeError("Unexpected RBAC bootstrap status.")

    return DeploymentPrerequisitesResult(
        status="ready",
        stage=None,
        commit_sha=None,
    )
