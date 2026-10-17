from dataclasses import dataclass

from kubernetes.client.exceptions import ApiException
from urllib3.exceptions import HTTPError


@dataclass(frozen=True)
class KubernetesAPIError:
    reason: str
    retryable: bool


def classify_kubernetes_api_error(
    error: Exception,
) -> KubernetesAPIError:
    """
    Classify Kubernetes API failures without exposing
    credentials, response bodies, or internal URLs.
    """

    if isinstance(error, ApiException):
        status = error.status

        if status == 401:
            return KubernetesAPIError(
                reason="authentication_failed",
                retryable=False,
            )

        if status == 403:
            return KubernetesAPIError(
                reason="permission_denied",
                retryable=False,
            )

        if status == 404:
            return KubernetesAPIError(
                reason="resource_not_found",
                retryable=False,
            )

        if status == 429:
            return KubernetesAPIError(
                reason="rate_limited",
                retryable=True,
            )

        if isinstance(status, int) and status >= 500:
            return KubernetesAPIError(
                reason="api_server_unavailable",
                retryable=True,
            )

        return KubernetesAPIError(
            reason="kubernetes_api_error",
            retryable=False,
        )

    if isinstance(error, (HTTPError, TimeoutError, ConnectionError)):
        return KubernetesAPIError(
            reason="connection_failed",
            retryable=True,
        )

    return KubernetesAPIError(
        reason="unexpected_observation_error",
        retryable=False,
    )
