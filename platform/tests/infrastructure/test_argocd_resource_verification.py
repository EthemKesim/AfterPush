from copy import deepcopy

import pytest

from afterpush_api.services.argocd_resource_verification import (
    verify_argocd_deployment_resource,
)


NAME = "example-api"
NAMESPACE = "ap-dev-example"


def make_application():
    return {
        "status": {
            "resources": [
                {
                    "group": "apps",
                    "version": "v1",
                    "kind": "Deployment",
                    "name": NAME,
                    "namespace": NAMESPACE,
                },
            ],
        },
    }


def make_deployment():
    return {
        "apiVersion": "apps/v1",
        "kind": "Deployment",
        "metadata": {
            "name": NAME,
            "namespace": NAMESPACE,
        },
    }


def verify(application=None, deployment=None, **kwargs):
    return verify_argocd_deployment_resource(
        make_application() if application is None else application,
        make_deployment() if deployment is None else deployment,
        expected_name=kwargs.get("expected_name", NAME),
        expected_namespace=kwargs.get("expected_namespace", NAMESPACE),
    )


def test_valid_resource_is_verified():
    result = verify()

    assert result.verified is True
    assert result.reason == "verified"


@pytest.mark.parametrize("name", ["", None, 123])
def test_rejects_invalid_expected_name(name):
    with pytest.raises(ValueError, match="Invalid expected Deployment name"):
        verify(expected_name=name)


@pytest.mark.parametrize("namespace", ["", None, 123])
def test_rejects_invalid_expected_namespace(namespace):
    with pytest.raises(ValueError, match="Invalid expected Deployment namespace"):
        verify(expected_namespace=namespace)


@pytest.mark.parametrize("application,deployment", [
    ({}, None),
    (None, {}),
    ([], {}),
])
def test_invalid_snapshots_are_rejected(application, deployment):
    result = verify(application=application, deployment=deployment)

    assert result.verified is False


def test_missing_deployment_metadata():
    deployment = make_deployment()
    del deployment["metadata"]

    assert verify(deployment=deployment).reason == "invalid_deployment_metadata"


def test_wrong_deployment_name():
    deployment = make_deployment()
    deployment["metadata"]["name"] = "another-api"

    assert verify(deployment=deployment).reason == "deployment_name_mismatch"


def test_wrong_deployment_namespace():
    deployment = make_deployment()
    deployment["metadata"]["namespace"] = "another-namespace"

    assert verify(deployment=deployment).reason == "deployment_namespace_mismatch"


def test_wrong_deployment_kind():
    deployment = make_deployment()
    deployment["kind"] = "StatefulSet"

    assert verify(deployment=deployment).reason == "invalid_deployment_kind"


def test_wrong_deployment_api_version():
    deployment = make_deployment()
    deployment["apiVersion"] = "extensions/v1beta1"

    assert verify(deployment=deployment).reason == "invalid_deployment_api_version"


def test_missing_application_status():
    assert verify(application={}).reason == "missing_application_status"


def test_missing_resource_inventory():
    assert verify(application={"status": {}}).reason == "missing_resource_inventory"


def test_resource_not_in_inventory():
    application = make_application()
    application["status"]["resources"] = []

    assert verify(application=application).reason == "deployment_not_managed"


@pytest.mark.parametrize("field,value", [
    ("group", "batch"),
    ("version", "v1beta1"),
    ("kind", "Service"),
    ("name", "another-api"),
    ("namespace", "another-namespace"),
])
def test_inventory_resource_mismatch(field, value):
    application = make_application()
    application["status"]["resources"][0][field] = value

    result = verify(application=application)

    assert result.verified is False
    assert result.reason == "deployment_not_managed"


def test_ignores_invalid_inventory_entries():
    application = make_application()
    application["status"]["resources"] = [
        None,
        "invalid",
        {"kind": "Service"},
        application["status"]["resources"][0],
    ]

    assert verify(application=application).verified is True


def test_does_not_modify_snapshots():
    application = make_application()
    deployment = make_deployment()

    original_application = deepcopy(application)
    original_deployment = deepcopy(deployment)

    verify(application=application, deployment=deployment)

    assert application == original_application
    assert deployment == original_deployment
