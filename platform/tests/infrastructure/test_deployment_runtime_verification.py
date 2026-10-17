from copy import deepcopy
from uuid import UUID

import pytest

from afterpush_api.services.bootstrap import build_resource_name

from afterpush_api.services.argocd_identity import (
    build_argocd_application_identity,
)
from afterpush_api.services.deployment_runtime_verification import (
    verify_deployment_runtime,
)


REPOSITORY = "https://github.com/EthemKesim/AfterPush.git"
SHA = "a" * 40
OTHER_SHA = "b" * 40
REVISION = 5

PROJECT_ID = UUID("12345678-1234-5678-1234-567812345678")
APPLICATION_NAME = "example-api"
RESOURCE_NAME = build_resource_name(APPLICATION_NAME, PROJECT_ID)

IDENTITY = build_argocd_application_identity(
    PROJECT_ID,
    "example-api",
    "dev",
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
            "health": {
                "status": "Healthy",
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
            "operationState": {
                "phase": "Succeeded",
                "syncResult": {
                    "revisions": [SHA, SHA],
                },
            },
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
                "afterpush.dev/revision": "5",
            },
        },
        "spec": {
            "replicas": 2,
            "template": {
                "metadata": {
                    "annotations": {
                        "afterpush.dev/revision": "5",
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


def verify(application=None, deployment=None, **kwargs):
    parameters = {
        "application": (
            application if application is not None else make_application()
        ),
        "deployment": (
            deployment if deployment is not None else make_deployment()
        ),
        "identity": IDENTITY,
        "repository_url": REPOSITORY,
        "expected_commit_sha": SHA,
        "expected_revision": REVISION,
        "project_id": PROJECT_ID,
        "application_name": APPLICATION_NAME,
    }
    parameters.update(kwargs)
    return verify_deployment_runtime(**parameters)


def test_all_checks_pass():
    result = verify()

    assert result.status == "healthy"
    assert result.reason == "healthy"
    assert result.rollout_complete is True
    assert result.revision_verified is True


def test_wrong_application_name():
    application = make_application()
    application["metadata"]["name"] = "another-app"

    result = verify(application=application)

    assert result.status == "unverified"
    assert result.reason == "application_name_mismatch"
    assert result.revision_verified is False


def test_wrong_repository():
    application = make_application()
    application["spec"]["sources"][0]["repoURL"] = (
        "https://github.com/example/other.git"
    )

    result = verify(application=application)

    assert result.status == "unverified"
    assert result.reason == "repository_mismatch"


def test_wrong_values_path():
    application = make_application()
    application["spec"]["sources"][0]["helm"]["valueFiles"] = [
        "$values/gitops/apps/prod/other/values.yaml"
    ]

    result = verify(application=application)

    assert result.status == "unverified"
    assert result.reason == "values_path_mismatch"


def test_wrong_git_commit():
    application = make_application()
    application["status"]["sync"]["revisions"][1] = OTHER_SHA

    result = verify(application=application)

    assert result.status == "unverified"
    assert result.reason == "current_revision_mismatch"


def test_failed_sync():
    application = make_application()
    application["status"]["operationState"]["phase"] = "Failed"

    result = verify(application=application)

    assert result.status == "unverified"
    assert result.reason == "sync_not_successful"


def test_out_of_sync():
    application = make_application()
    application["status"]["sync"]["status"] = "OutOfSync"

    result = verify(application=application)

    assert result.status == "unverified"
    assert result.reason == "not_synced"


def test_degraded_application():
    application = make_application()
    application["status"]["health"]["status"] = "Degraded"

    result = verify(application=application)

    assert result.status == "degraded"
    assert result.rollout_complete is True


def test_incomplete_kubernetes_rollout():
    deployment = make_deployment()
    deployment["status"]["updatedReplicas"] = 1

    result = verify(deployment=deployment)

    assert result.status == "progressing"
    assert result.rollout_complete is False


def test_wrong_kubernetes_revision():
    deployment = make_deployment()
    deployment["metadata"]["annotations"]["afterpush.dev/revision"] = "4"

    result = verify(deployment=deployment)

    assert result.status == "revision_mismatch"
    assert result.rollout_complete is False
    assert result.revision_verified is False


def test_wrong_pod_template_revision():
    deployment = make_deployment()
    deployment["spec"]["template"]["metadata"]["annotations"][
        "afterpush.dev/revision"
    ] = "4"

    result = verify(deployment=deployment)

    assert result.status != "healthy"
    assert result.rollout_complete is False


def test_missing_kubernetes_revision():
    deployment = make_deployment()
    deployment["metadata"]["annotations"] = {}

    result = verify(deployment=deployment)

    assert result.status == "unverified"
    assert result.revision_verified is False


def test_does_not_modify_snapshots():
    application = make_application()
    deployment = make_deployment()

    original_application = deepcopy(application)
    original_deployment = deepcopy(deployment)

    verify(application=application, deployment=deployment)

    assert application == original_application
    assert deployment == original_deployment


@pytest.mark.parametrize("revision", [0, -1, "5", True])
def test_invalid_expected_revision(revision):
    with pytest.raises(ValueError, match="Invalid expected revision"):
        verify(expected_revision=revision)


def test_runtime_rejects_wrong_deployment_name():
    deployment = make_deployment()
    deployment["metadata"]["name"] = "another-api"

    result = verify(deployment=deployment)

    assert result.status == "unverified"
    assert result.reason == "deployment_name_mismatch"
    assert result.revision_verified is False


def test_runtime_rejects_wrong_deployment_namespace():
    deployment = make_deployment()
    deployment["metadata"]["namespace"] = "default"

    result = verify(deployment=deployment)

    assert result.status == "unverified"
    assert result.reason == "deployment_namespace_mismatch"


def test_runtime_rejects_wrong_resource_kind():
    deployment = make_deployment()
    deployment["kind"] = "StatefulSet"

    result = verify(deployment=deployment)

    assert result.status == "unverified"
    assert result.reason == "invalid_deployment_kind"


def test_runtime_rejects_missing_argocd_inventory():
    application = make_application()
    del application["status"]["resources"]

    result = verify(application=application)

    assert result.status == "unverified"
    assert result.reason == "missing_resource_inventory"


def test_runtime_rejects_unmanaged_deployment():
    application = make_application()
    application["status"]["resources"][0]["name"] = "another-api"

    result = verify(application=application)

    assert result.status == "unverified"
    assert result.reason == "deployment_not_managed"


def test_runtime_rejects_resource_from_another_project():
    other_project_id = UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")

    result = verify(project_id=other_project_id)

    assert result.status == "unverified"
    assert result.reason == "deployment_name_mismatch"
    assert result.revision_verified is False
