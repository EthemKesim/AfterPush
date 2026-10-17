from dataclasses import dataclass
from typing import Callable
from uuid import UUID

from afterpush_api.services.namespace_bootstrap_readiness import (
    NamespaceBootstrapNotReady,
    verify_namespace_bootstrap,
)


@dataclass(frozen=True)
class NamespaceGateTarget:
    project_id: UUID
    application_name: str
    environment: str


def check_deployment_namespace(
    *,
    target: NamespaceGateTarget,
    core_api,
    verifier: Callable = verify_namespace_bootstrap,
) -> str:
    if core_api is None:
        raise NamespaceBootstrapNotReady(
            "Kubernetes CoreV1Api is not configured."
        )

    return verifier(
        core_api=core_api,
        project_id=target.project_id,
        application_name=target.application_name,
        environment=target.environment,
    )
