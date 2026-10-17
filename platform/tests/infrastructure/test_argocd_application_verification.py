from copy import deepcopy
from uuid import UUID

import pytest

from afterpush_api.services.argocd_identity import (
    build_argocd_application_identity,
)
from afterpush_api.services.argocd_application_verification import (
    verify_argocd_application,
)


REPOSITORY = "https://github.com/EthemKesim/AfterPush.git"

IDENTITY = build_argocd_application_identity(
    UUID("12345678-1234-5678-1234-567812345678"),
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
    }


def verify(application):
    return verify_argocd_application(
        application,
        IDENTITY,
        REPOSITORY,
    )


def test_valid_application_is_verified():
    result = verify(make_application())

    assert result.verified is True
    assert result.reason == "verified"


@pytest.mark.parametrize("repository", ["", " ", None, 123])
def test_invalid_repository_is_rejected(repository):
    with pytest.raises(ValueError, match="Invalid GitOps repository URL"):
        verify_argocd_application(
            make_application(),
            IDENTITY,
            repository,
        )


def test_invalid_application_is_rejected():
    assert verify(None).reason == "invalid_application"


@pytest.mark.parametrize("application", [
    {},
    {"metadata": {}},
    {"spec": {}},
])
def test_invalid_structure_is_rejected(application):
    assert verify(application).reason == "invalid_structure"


def test_wrong_application_name():
    application = make_application()
    application["metadata"]["name"] = "another-application"

    assert verify(application).reason == "application_name_mismatch"


def test_wrong_application_namespace():
    application = make_application()
    application["metadata"]["namespace"] = "default"

    assert verify(application).reason == "application_namespace_mismatch"


def test_missing_destination():
    application = make_application()
    del application["spec"]["destination"]

    assert verify(application).reason == "missing_destination"


def test_wrong_destination_namespace():
    application = make_application()
    application["spec"]["destination"]["namespace"] = "another-namespace"

    assert verify(application).reason == "destination_namespace_mismatch"


def test_wrong_destination_server():
    application = make_application()
    application["spec"]["destination"]["server"] = "https://example.com"

    assert verify(application).reason == "destination_server_mismatch"


@pytest.mark.parametrize("sources", [
    [],
    [{}],
    [{}, {}, {}],
    None,
])
def test_invalid_source_count(sources):
    application = make_application()
    application["spec"]["sources"] = sources

    assert verify(application).reason == "invalid_sources"


def test_invalid_source_structure():
    application = make_application()
    application["spec"]["sources"][1] = None

    assert verify(application).reason == "invalid_source_structure"


@pytest.mark.parametrize("source_index", [0, 1])
def test_wrong_repository(source_index):
    application = make_application()
    application["spec"]["sources"][source_index]["repoURL"] = (
        "https://github.com/example/other.git"
    )

    assert verify(application).reason == "repository_mismatch"


@pytest.mark.parametrize("source_index", [0, 1])
def test_wrong_branch(source_index):
    application = make_application()
    application["spec"]["sources"][source_index]["targetRevision"] = "develop"

    assert verify(application).reason == "branch_mismatch"


def test_wrong_chart_path():
    application = make_application()
    application["spec"]["sources"][0]["path"] = "helm/other"

    assert verify(application).reason == "chart_path_mismatch"


def test_missing_helm_config():
    application = make_application()
    del application["spec"]["sources"][0]["helm"]

    assert verify(application).reason == "missing_helm_config"


def test_wrong_values_path():
    application = make_application()
    application["spec"]["sources"][0]["helm"]["valueFiles"] = [
        "$values/gitops/apps/prod/other/values.yaml"
    ]

    assert verify(application).reason == "values_path_mismatch"


def test_wrong_values_reference():
    application = make_application()
    application["spec"]["sources"][1]["ref"] = "other"

    assert verify(application).reason == "values_reference_mismatch"


@pytest.mark.parametrize("field,value", [
    ("path", "another/path"),
    ("chart", "another-chart"),
])
def test_unexpected_values_source(field, value):
    application = make_application()
    application["spec"]["sources"][1][field] = value

    assert verify(application).reason == "unexpected_values_source"


@pytest.mark.parametrize("field,value", [
    ("ref", "other"),
    ("chart", "another-chart"),
])
def test_unexpected_chart_source(field, value):
    application = make_application()
    application["spec"]["sources"][0][field] = value

    assert verify(application).reason == "unexpected_chart_source"


def test_wrong_argocd_project():
    application = make_application()
    application["spec"]["project"] = "other-project"

    assert verify(application).reason == "project_mismatch"


def test_does_not_modify_application():
    application = make_application()
    original = deepcopy(application)

    verify(application)

    assert application == original
