from dataclasses import dataclass
from uuid import UUID

from kubernetes.client.exceptions import ApiException
from urllib3.exceptions import HTTPError

from afterpush_api.services.argocd_identity import (
    build_argocd_application_identity,
)
from afterpush_api.services.bootstrap import build_resource_name
from afterpush_api.services.deployment_runtime_verification import (
    DeploymentRuntimeVerification,
    verify_deployment_runtime,
)
from afterpush_api.services.kubernetes_api_errors import (
    classify_kubernetes_api_error,
)
from afterpush_api.services.kubernetes_reader import KubernetesReader


@dataclass(frozen=True)
class KubernetesRuntimeRequest:
    project_id: UUID
    application_name: str
    environment: str
    repository_url: str
    expected_commit_sha: str
    expected_revision: int


class KubernetesRuntimeObserver:
    """
    Read ArgoCD and Kubernetes snapshots and evaluate runtime status.

    Known API and connection failures become unverified results.
    Unexpected programming errors are propagated.
    """

    def __init__(self, reader: KubernetesReader) -> None:
        self._reader = reader

    def observe(
        self,
        request: KubernetesRuntimeRequest,
    ) -> DeploymentRuntimeVerification:
        identity = build_argocd_application_identity(
            project_id=request.project_id,
            application_name=request.application_name,
            environment=request.environment,
        )

        deployment_name = build_resource_name(
            request.application_name,
            request.project_id,
        )

        try:
            application = self._reader.read_argocd_application(
                identity.application_name,
            )

            deployment = self._reader.read_deployment(
                namespace=identity.namespace,
                deployment_name=deployment_name,
            )
        except (ApiException, HTTPError, TimeoutError, ConnectionError) as error:
            classified = classify_kubernetes_api_error(error)

            return DeploymentRuntimeVerification(
                status="unverified",
                reason=classified.reason,
                rollout_complete=False,
                revision_verified=False,
            )

        return verify_deployment_runtime(
            application=application,
            deployment=deployment,
            identity=identity,
            repository_url=request.repository_url,
            expected_commit_sha=request.expected_commit_sha,
            expected_revision=request.expected_revision,
            project_id=request.project_id,
            application_name=request.application_name,
        )
