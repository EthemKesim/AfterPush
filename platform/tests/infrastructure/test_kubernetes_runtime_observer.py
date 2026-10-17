from unittest.mock import Mock
from uuid import UUID

import pytest

from afterpush_api.services.argocd_identity import (
    build_argocd_application_identity,
)
from afterpush_api.services.bootstrap import build_resource_name
from afterpush_api.services.kubernetes_runtime_observer import (
    KubernetesRuntimeObserver,
    KubernetesRuntimeRequest,
)


PROJECT_ID = UUID("12345678-1234-5678-1234-567812345678")
APPLICATION_NAME = "example-api"
REPOSITORY = "https://github.com/EthemKesim/AfterPush.git"
SHA = "a" * 40
REVISION = 5

IDENTITY = build_argocd_application_identity(
    PROJECT_ID,
    APPLICATION_NAME,
    "dev",
)

RESOURCE_NAME = build_resource_name(
    APPLICATION_NAME,
    PROJECT_ID,
)


def make_request():
    return KubernetesRuntimeRequest(
        project_id=PROJECT_ID,
        application_name=APPLICATION_NAME,
        environment="dev",
        repository_url=REPOSITORY,
        expected_commit_sha=SHA,
        expected_revision=REVISION,
    )


def make_application():
    return {
        "metadata": {
            "name": IDENTITY.application_name,
            "namespace": "argocd",
        },
        "spec": {
            "project": "default",
            "sources": [
                {
                    "repoURL": REPOSITORY,
                    "targetRevision": "main",
                    "path": "helm/afterpush",
                    "helm": {
                        "valueFiles": [
                            f"$values/{IDENTITY.gitops_path}/values.yaml"
                        ],
                    },
                },
                {
                    "repoURL": REPOSITORY,
                    "targetRevision": "main",
                    "ref": "values",
                },
            ],
            "destination": {
                "server": "https://kubernetes.default.svc",
                "namespace": IDENTITY.namespace,
            },
        },
        "status": {
            "sync": {
                "status": "Synced",
                "revisions": [SHA, SHA],
            },
            "health": {"status": "Healthy"},
            "operationState": {
                "phase": "Succeeded",
                "syncResult": {
                    "revisions": [SHA, SHA],
                },
            },
            "resources": [
                {
                    "group": "apps",
                    "version": "v1",
                    "kind": "Deployment",
                    "name": RESOURCE_NAME,
                    "namespace": IDENTITY.namespace,
                },
            ],
        },
    }


def make_deployment():
    return {
        "apiVersion": "apps/v1",
        "kind": "Deployment",
        "metadata": {
            "name": RESOURCE_NAME,
            "namespace": IDENTITY.namespace,
            "generation": 8,
            "annotations": {
                "afterpush.dev/revision": str(REVISION),
            },
        },
        "spec": {
            "replicas": 2,
            "template": {
                "metadata": {
                    "annotations": {
                        "afterpush.dev/revision": str(REVISION),
                    },
                },
            },
        },
        "status": {
            "observedGeneration": 8,
            "replicas": 2,
            "updatedReplicas": 2,
            "readyReplicas": 2,
            "availableReplicas": 2,
        },
    }


def make_observer():
    reader = Mock()
    reader.read_argocd_application.return_value = make_application()
    reader.read_deployment.return_value = make_deployment()

    return KubernetesRuntimeObserver(reader), reader


def test_observes_healthy_deployment():
    observer, reader = make_observer()

    result = observer.observe(make_request())

    assert result.status == "healthy"
    assert result.rollout_complete is True
    assert result.revision_verified is True

    reader.read_argocd_application.assert_called_once_with(
        IDENTITY.application_name,
    )
    reader.read_deployment.assert_called_once_with(
        namespace=IDENTITY.namespace,
        deployment_name=RESOURCE_NAME,
    )


def test_rejects_wrong_deployment_identity():
    observer, reader = make_observer()

    deployment = make_deployment()
    deployment["metadata"]["name"] = "another-api"
    reader.read_deployment.return_value = deployment

    result = observer.observe(make_request())

    assert result.status == "unverified"
    assert result.reason == "deployment_name_mismatch"


def test_rejects_unmanaged_deployment():
    observer, reader = make_observer()

    application = make_application()
    application["status"]["resources"] = []
    reader.read_argocd_application.return_value = application

    result = observer.observe(make_request())

    assert result.status == "unverified"
    assert result.reason == "deployment_not_managed"


def test_reports_incomplete_rollout():
    observer, reader = make_observer()

    deployment = make_deployment()
    deployment["status"]["readyReplicas"] = 1
    reader.read_deployment.return_value = deployment

    result = observer.observe(make_request())

    assert result.status == "progressing"
    assert result.rollout_complete is False


def test_propagates_argocd_api_error():
    observer, reader = make_observer()
    reader.read_argocd_application.side_effect = RuntimeError(
        "ArgoCD API unavailable"
    )

    with pytest.raises(RuntimeError, match="ArgoCD API unavailable"):
        observer.observe(make_request())

    reader.read_deployment.assert_not_called()


def test_propagates_deployment_api_error():
    observer, reader = make_observer()
    reader.read_deployment.side_effect = RuntimeError(
        "Kubernetes Deployment API unavailable"
    )

    with pytest.raises(RuntimeError, match="Kubernetes Deployment API unavailable"):
        observer.observe(make_request())


def test_rejects_unsupported_environment_before_api_calls():
    observer, reader = make_observer()
    request = KubernetesRuntimeRequest(
        project_id=PROJECT_ID,
        application_name=APPLICATION_NAME,
        environment="production",
        repository_url=REPOSITORY,
        expected_commit_sha=SHA,
        expected_revision=REVISION,
    )

    with pytest.raises(ValueError, match="Unsupported deployment environment"):
        observer.observe(request)

    reader.read_argocd_application.assert_not_called()
    reader.read_deployment.assert_not_called()


@pytest.mark.parametrize(
    "status,expected_reason",
    [
        (401, "authentication_failed"),
        (403, "permission_denied"),
        (404, "resource_not_found"),
        (429, "rate_limited"),
        (500, "api_server_unavailable"),
        (503, "api_server_unavailable"),
    ],
)
@pytest.mark.parametrize(
    "failing_method",
    ["read_argocd_application", "read_deployment"],
)
def test_observer_handles_kubernetes_api_errors(
    status,
    expected_reason,
    failing_method,
):
    from kubernetes.client.exceptions import ApiException

    observer, reader = make_observer()

    getattr(reader, failing_method).side_effect = ApiException(
        status=status,
    )

    result = observer.observe(make_request())

    assert result.status == "unverified"
    assert result.reason == expected_reason
    assert result.rollout_complete is False
    assert result.revision_verified is False

    if failing_method == "read_argocd_application":
        reader.read_deployment.assert_not_called()


@pytest.mark.parametrize(
    "error",
    [
        TimeoutError("Connection timed out"),
        ConnectionError("Connection refused"),
    ],
)
def test_observer_handles_connection_errors(error):
    observer, reader = make_observer()
    reader.read_deployment.side_effect = error

    result = observer.observe(make_request())

    assert result.status == "unverified"
    assert result.reason == "connection_failed"
    assert result.revision_verified is False


def test_observer_does_not_expose_sensitive_api_error_details():
    from kubernetes.client.exceptions import ApiException

    observer, reader = make_observer()

    error = ApiException(
        status=403,
        reason="Sensitive internal API information",
    )
    error.body = "SECRET_TOKEN_EXAMPLE"

    reader.read_argocd_application.side_effect = error

    result = observer.observe(make_request())

    assert result.status == "unverified"
    assert result.reason == "permission_denied"
    assert "SECRET_TOKEN_EXAMPLE" not in result.reason
    assert "Sensitive internal API information" not in result.reason


def test_observer_does_not_hide_programming_errors():
    observer, reader = make_observer()

    reader.read_deployment.side_effect = TypeError(
        "Unexpected programming error"
    )

    with pytest.raises(TypeError, match="Unexpected programming error"):
        observer.observe(make_request())
