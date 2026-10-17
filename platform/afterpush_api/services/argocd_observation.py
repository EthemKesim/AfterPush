from dataclasses import dataclass
from typing import Any


SYNC_STATUSES = frozenset({
    "Synced",
    "OutOfSync",
    "Unknown",
})

HEALTH_STATUSES = frozenset({
    "Healthy",
    "Progressing",
    "Degraded",
    "Suspended",
    "Missing",
    "Unknown",
})


@dataclass(frozen=True)
class ArgoCDObservation:
    sync_status: str
    health_status: str
    source_revisions: tuple[str, ...]


def parse_argocd_observation(
    application: dict[str, Any],
) -> ArgoCDObservation:
    """
    Parse ArgoCD Application status.

    This does not establish whether a specific AfterPush
    deployment revision has reached Kubernetes.
    """

    if not isinstance(application, dict):
        raise ValueError("Invalid ArgoCD Application response")

    status = application.get("status")

    if not isinstance(status, dict):
        raise ValueError("Missing ArgoCD Application status")

    sync = status.get("sync")
    health = status.get("health")

    if not isinstance(sync, dict):
        raise ValueError("Invalid ArgoCD sync status")

    if not isinstance(health, dict):
        raise ValueError("Invalid ArgoCD health status")

    sync_status = sync.get("status")
    health_status = health.get("status")

    if sync_status not in SYNC_STATUSES:
        raise ValueError("Unsupported ArgoCD sync status")

    if health_status not in HEALTH_STATUSES:
        raise ValueError("Unsupported ArgoCD health status")

    revisions = sync.get("revisions")

    if revisions is None:
        revision = sync.get("revision")
        revisions = [revision] if revision is not None else []

    if not isinstance(revisions, list) or not all(
        isinstance(revision, str) and revision.strip()
        for revision in revisions
    ):
        raise ValueError("Invalid ArgoCD source revisions")

    return ArgoCDObservation(
        sync_status=sync_status,
        health_status=health_status,
        source_revisions=tuple(revisions),
    )
