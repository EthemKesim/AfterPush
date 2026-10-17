from dataclasses import dataclass
from typing import Any


REVISION_ANNOTATION = "afterpush.dev/revision"


@dataclass(frozen=True)
class KubernetesRolloutObservation:
    observed_revision: int | None
    desired_replicas: int
    updated_replicas: int
    ready_replicas: int
    available_replicas: int
    rollout_complete: bool


def _nonnegative_int(value: Any) -> bool:
    return type(value) is int and value >= 0


def _parse_revision(value: Any) -> int | None:
    if (
        isinstance(value, str)
        and value.isascii()
        and value.isdecimal()
        and int(value) >= 1
    ):
        return int(value)

    return None


def evaluate_kubernetes_rollout(
    deployment: dict[str, Any],
    expected_revision: int,
) -> KubernetesRolloutObservation:
    """
    Evaluate a Kubernetes Deployment snapshot.

    A complete rollout requires matching revision annotations
    on both the Deployment and its pod template.

    This does not independently verify ArgoCD synchronization,
    individual Pods, or application-level functionality.
    """

    if type(expected_revision) is not int or expected_revision < 1:
        raise ValueError("Invalid expected revision")

    if not isinstance(deployment, dict):
        raise ValueError("Invalid Kubernetes Deployment")

    metadata = deployment.get("metadata")
    spec = deployment.get("spec")
    status = deployment.get("status")

    if not all(
        isinstance(section, dict)
        for section in (metadata, spec, status)
    ):
        raise ValueError("Invalid Kubernetes Deployment structure")

    annotations = metadata.get("annotations") or {}

    if not isinstance(annotations, dict):
        raise ValueError("Invalid Deployment annotations")

    observed_revision = _parse_revision(
        annotations.get(REVISION_ANNOTATION)
    )

    template = spec.get("template")

    template_revision = None

    if isinstance(template, dict):
        template_metadata = template.get("metadata")

        if isinstance(template_metadata, dict):
            template_annotations = (
                template_metadata.get("annotations") or {}
            )

            if not isinstance(template_annotations, dict):
                raise ValueError("Invalid pod template annotations")

            template_revision = _parse_revision(
                template_annotations.get(REVISION_ANNOTATION)
            )

    generation = metadata.get("generation")
    observed_generation = status.get("observedGeneration", 0)

    desired = spec.get("replicas", 1)
    updated = status.get("updatedReplicas", 0)
    ready = status.get("readyReplicas", 0)
    available = status.get("availableReplicas", 0)
    total = status.get("replicas", 0)

    if not all(
        _nonnegative_int(value)
        for value in (
            generation,
            observed_generation,
            desired,
            updated,
            ready,
            available,
            total,
        )
    ):
        raise ValueError("Invalid Kubernetes replica or generation data")

    rollout_complete = (
        observed_revision == expected_revision
        and template_revision == expected_revision
        and generation >= 1
        and observed_generation >= generation
        and desired >= 1
        and updated == desired
        and ready == desired
        and available == desired
        and total == desired
    )

    return KubernetesRolloutObservation(
        observed_revision=observed_revision,
        desired_replicas=desired,
        updated_replicas=updated,
        ready_replicas=ready,
        available_replicas=available,
        rollout_complete=rollout_complete,
    )
