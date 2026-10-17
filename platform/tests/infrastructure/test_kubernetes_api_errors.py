import pytest

from kubernetes.client.exceptions import ApiException
from urllib3.exceptions import (
    HTTPError,
    MaxRetryError,
    NewConnectionError,
)

from afterpush_api.services.kubernetes_api_errors import (
    KubernetesAPIError,
    classify_kubernetes_api_error,
)


@pytest.mark.parametrize(
    "status,reason,retryable",
    [
        (401, "authentication_failed", False),
        (403, "permission_denied", False),
        (404, "resource_not_found", False),
        (429, "rate_limited", True),
        (500, "api_server_unavailable", True),
        (502, "api_server_unavailable", True),
        (503, "api_server_unavailable", True),
        (504, "api_server_unavailable", True),
        (400, "kubernetes_api_error", False),
        (409, "kubernetes_api_error", False),
    ],
)
def test_classifies_kubernetes_api_status(
    status,
    reason,
    retryable,
):
    result = classify_kubernetes_api_error(
        ApiException(status=status)
    )

    assert result == KubernetesAPIError(
        reason=reason,
        retryable=retryable,
    )


@pytest.mark.parametrize(
    "error",
    [
        TimeoutError("Request timed out"),
        ConnectionError("Connection refused"),
        HTTPError("HTTP connection failed"),
    ],
)
def test_classifies_connection_errors(error):
    result = classify_kubernetes_api_error(error)

    assert result.reason == "connection_failed"
    assert result.retryable is True


def test_classifies_urllib3_connection_failure():
    pool = object()

    error = MaxRetryError(
        pool,
        "/apis/apps/v1",
        reason=NewConnectionError(
            None,
            "Connection refused",
        ),
    )

    result = classify_kubernetes_api_error(error)

    assert result.reason == "connection_failed"
    assert result.retryable is True


def test_classifies_unexpected_error():
    result = classify_kubernetes_api_error(
        RuntimeError("Unexpected internal failure")
    )

    assert result.reason == "unexpected_observation_error"
    assert result.retryable is False


def test_does_not_expose_api_response_body():
    error = ApiException(
        status=403,
        reason="Sensitive internal details",
    )
    error.body = "SECRET_TOKEN_EXAMPLE"

    result = classify_kubernetes_api_error(error)

    assert result.reason == "permission_denied"
    assert "SECRET_TOKEN_EXAMPLE" not in result.reason
    assert "Sensitive internal details" not in result.reason
