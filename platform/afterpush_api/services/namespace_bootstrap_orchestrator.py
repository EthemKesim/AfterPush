"""Coordinate namespace bootstrap without publishing workloads."""

from dataclasses import dataclass
from typing import Callable, Literal

from afterpush_api.services.namespace_bootstrap_publication import (
    NamespaceBootstrapPublicationSpec,
    publish_namespace_bootstrap,
)
from afterpush_api.services.namespace_bootstrap_readiness import (
    NamespaceBootstrapNotReady,
    verify_namespace_bootstrap,
)


BootstrapStatus = Literal["ready", "waiting"]


@dataclass(frozen=True)
class NamespaceBootstrapResult:
    status: BootstrapStatus
    namespace: str | None
    commit_sha: str | None


def reconcile_namespace_bootstrap(
    *,
    repository_url: str,
    spec: NamespaceBootstrapPublicationSpec,
    core_api,
    verifier: Callable = verify_namespace_bootstrap,
    publisher: Callable = publish_namespace_bootstrap,
) -> NamespaceBootstrapResult:
    """
    Ensure namespace bootstrap is requested before workload publication.

    A ready namespace requires no GitOps publication.

    If the namespace is not ready, publish its bootstrap manifest
    and return 'waiting'. Publication does not imply Kubernetes
    readiness.

    This function does not publish workloads or update database state.
    """

    if not repository_url or not repository_url.strip():
        raise ValueError("GitOps repository URL cannot be empty.")

    if not isinstance(spec, NamespaceBootstrapPublicationSpec):
        raise TypeError(
            "spec must be a NamespaceBootstrapPublicationSpec."
        )

    if core_api is None:
        raise NamespaceBootstrapNotReady(
            "Kubernetes CoreV1Api is not configured."
        )

    try:
        namespace = verifier(
            core_api=core_api,
            project_id=spec.project_id,
            application_name=spec.application_name,
            environment=spec.environment,
        )

    except NamespaceBootstrapNotReady:
        commit_sha = publisher(
            repository_url=repository_url,
            spec=spec,
        )

        if not commit_sha:
            raise RuntimeError(
                "Bootstrap publisher returned no commit SHA."
            )

        return NamespaceBootstrapResult(
            status="waiting",
            namespace=None,
            commit_sha=commit_sha,
        )

    return NamespaceBootstrapResult(
        status="ready",
        namespace=namespace,
        commit_sha=None,
    )
