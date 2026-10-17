import json
from unittest.mock import Mock

import pytest

from afterpush_api.services.kubernetes_reader import (
    KubernetesReader,
)


def make_reader():
    custom_objects_api = Mock()
    apps_api = Mock()

    reader = KubernetesReader(
        custom_objects_api=custom_objects_api,
        apps_api=apps_api,
    )

    return reader, custom_objects_api, apps_api


def test_reads_argocd_application():
    reader, custom_api, _ = make_reader()

    expected = {
        "metadata": {
            "name": "ap-dev-example",
            "namespace": "argocd",
        },
        "status": {"sync": {"status": "Synced"}},
    }

    custom_api.get_namespaced_custom_object.return_value = expected

    result = reader.read_argocd_application("ap-dev-example")

    assert result == expected

    custom_api.get_namespaced_custom_object.assert_called_once_with(
        group="argoproj.io",
        version="v1alpha1",
        namespace="argocd",
        plural="applications",
        name="ap-dev-example",
    )


def test_reads_kubernetes_deployment():
    reader, _, apps_api = make_reader()

    expected = {
        "apiVersion": "apps/v1",
        "kind": "Deployment",
        "metadata": {
            "name": "example-api",
            "namespace": "ap-dev-example",
        },
        "status": {"readyReplicas": 2},
    }

    response = Mock()
    response.data = json.dumps(expected).encode("utf-8")

    apps_api.read_namespaced_deployment.return_value = response

    result = reader.read_deployment(
        namespace="ap-dev-example",
        deployment_name="example-api",
    )

    assert result == expected

    apps_api.read_namespaced_deployment.assert_called_once_with(
        name="example-api",
        namespace="ap-dev-example",
        _preload_content=False,
    )


@pytest.mark.parametrize("name", ["", None, 123])
def test_rejects_invalid_application_name(name):
    reader, custom_api, _ = make_reader()

    with pytest.raises(ValueError, match="Invalid ArgoCD Application name"):
        reader.read_argocd_application(name)

    custom_api.get_namespaced_custom_object.assert_not_called()


@pytest.mark.parametrize("namespace", ["", None, 123])
def test_rejects_invalid_namespace(namespace):
    reader, _, apps_api = make_reader()

    with pytest.raises(ValueError, match="Invalid Kubernetes namespace"):
        reader.read_deployment(
            namespace=namespace,
            deployment_name="example-api",
        )

    apps_api.read_namespaced_deployment.assert_not_called()


@pytest.mark.parametrize("name", ["", None, 123])
def test_rejects_invalid_deployment_name(name):
    reader, _, apps_api = make_reader()

    with pytest.raises(ValueError, match="Invalid Kubernetes Deployment name"):
        reader.read_deployment(
            namespace="default",
            deployment_name=name,
        )

    apps_api.read_namespaced_deployment.assert_not_called()


def test_rejects_invalid_argocd_response():
    reader, custom_api, _ = make_reader()
    custom_api.get_namespaced_custom_object.return_value = None

    with pytest.raises(ValueError, match="Invalid ArgoCD Application response"):
        reader.read_argocd_application("ap-dev-example")


def test_rejects_invalid_deployment_json():
    reader, _, apps_api = make_reader()

    response = Mock()
    response.data = b"invalid-json"

    apps_api.read_namespaced_deployment.return_value = response

    with pytest.raises(json.JSONDecodeError):
        reader.read_deployment(
            namespace="default",
            deployment_name="example-api",
        )


def test_propagates_kubernetes_api_error():
    reader, custom_api, _ = make_reader()

    custom_api.get_namespaced_custom_object.side_effect = RuntimeError(
        "Kubernetes API unavailable"
    )

    with pytest.raises(RuntimeError, match="Kubernetes API unavailable"):
        reader.read_argocd_application("ap-dev-example")


def test_rejects_wrong_argocd_application_name():
    reader, custom_api, _ = make_reader()
    custom_api.get_namespaced_custom_object.return_value = {
        "metadata": {
            "name": "another-application",
            "namespace": "argocd",
        },
    }

    with pytest.raises(ValueError, match="ArgoCD Application identity mismatch"):
        reader.read_argocd_application("ap-dev-example")


def test_rejects_wrong_argocd_namespace():
    reader, custom_api, _ = make_reader()
    custom_api.get_namespaced_custom_object.return_value = {
        "metadata": {
            "name": "ap-dev-example",
            "namespace": "default",
        },
    }

    with pytest.raises(ValueError, match="ArgoCD Application identity mismatch"):
        reader.read_argocd_application("ap-dev-example")


@pytest.mark.parametrize(
    "field,value",
    [
        ("name", "another-api"),
        ("namespace", "default"),
    ],
)
def test_rejects_wrong_deployment_identity(field, value):
    reader, _, apps_api = make_reader()

    deployment = {
        "apiVersion": "apps/v1",
        "kind": "Deployment",
        "metadata": {
            "name": "example-api",
            "namespace": "ap-dev-example",
        },
    }
    deployment["metadata"][field] = value

    response = Mock()
    response.data = json.dumps(deployment).encode("utf-8")
    apps_api.read_namespaced_deployment.return_value = response

    with pytest.raises(ValueError, match="Kubernetes Deployment identity mismatch"):
        reader.read_deployment(
            namespace="ap-dev-example",
            deployment_name="example-api",
        )


@pytest.mark.parametrize(
    "field,value",
    [
        ("apiVersion", "v1"),
        ("kind", "Service"),
    ],
)
def test_rejects_wrong_deployment_resource_type(field, value):
    reader, _, apps_api = make_reader()

    deployment = {
        "apiVersion": "apps/v1",
        "kind": "Deployment",
        "metadata": {
            "name": "example-api",
            "namespace": "ap-dev-example",
        },
    }
    deployment[field] = value

    response = Mock()
    response.data = json.dumps(deployment).encode("utf-8")
    apps_api.read_namespaced_deployment.return_value = response

    with pytest.raises(ValueError, match="Invalid Kubernetes Deployment resource type"):
        reader.read_deployment(
            namespace="ap-dev-example",
            deployment_name="example-api",
        )


def test_rejects_json_array_as_deployment():
    reader, _, apps_api = make_reader()

    response = Mock()
    response.data = b"[]"
    apps_api.read_namespaced_deployment.return_value = response

    with pytest.raises(ValueError, match="Invalid Kubernetes Deployment response"):
        reader.read_deployment(
            namespace="default",
            deployment_name="example-api",
        )


def test_propagates_deployment_api_error():
    reader, _, apps_api = make_reader()

    apps_api.read_namespaced_deployment.side_effect = RuntimeError(
        "Kubernetes Deployment API unavailable"
    )

    with pytest.raises(RuntimeError, match="Kubernetes Deployment API unavailable"):
        reader.read_deployment(
            namespace="default",
            deployment_name="example-api",
        )
