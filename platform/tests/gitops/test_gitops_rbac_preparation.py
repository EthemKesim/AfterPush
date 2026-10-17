from uuid import uuid4

import pytest
import yaml

from afterpush_api.services.argocd_identity import (
    build_argocd_application_identity,
)
from afterpush_api.services.bootstrap import build_resource_name
from afterpush_api.services.gitops_rbac_preparation import (
    prepare_gitops_rbac,
)


@pytest.fixture
def prepared(tmp_path):
    project_id = uuid4()

    paths = prepare_gitops_rbac(
        repository_root=tmp_path,
        project_id=project_id,
        application_name="payment-api",
        environment="dev",
    )

    return project_id, paths


def test_creates_expected_files(tmp_path, prepared):
    project_id, paths = prepared

    expected_directory = (
        tmp_path.resolve()
        / "gitops/platform/rbac/projects/dev"
        / str(project_id)
        / "payment-api"
    )

    assert paths == (
        expected_directory / "argocd-rbac.yaml",
        expected_directory / "deployment-rbac.yaml",
    )
    assert all(path.is_file() for path in paths)


def test_argocd_rbac_is_read_only(prepared):
    project_id, paths = prepared

    identity = build_argocd_application_identity(
        project_id=project_id,
        application_name="payment-api",
        environment="dev",
    )

    role, binding = list(
        yaml.safe_load_all(paths[0].read_text(encoding="utf-8"))
    )

    assert role["kind"] == "Role"
    assert role["metadata"]["namespace"] == "argocd"
    assert role["rules"] == [
        {
            "apiGroups": ["argoproj.io"],
            "resources": ["applications"],
            "resourceNames": [identity.application_name],
            "verbs": ["get"],
        }
    ]

    assert binding["kind"] == "RoleBinding"
    assert binding["metadata"]["namespace"] == "argocd"
    assert binding["subjects"] == [
        {
            "kind": "ServiceAccount",
            "name": "afterpush-runtime-worker",
            "namespace": "afterpush-system",
        }
    ]


def test_deployment_rbac_is_resource_scoped(prepared):
    project_id, paths = prepared

    identity = build_argocd_application_identity(
        project_id=project_id,
        application_name="payment-api",
        environment="dev",
    )

    deployment_name = build_resource_name(
        "payment-api",
        project_id,
    )

    role, binding = list(
        yaml.safe_load_all(paths[1].read_text(encoding="utf-8"))
    )

    assert role["kind"] == "Role"
    assert role["metadata"]["namespace"] == identity.namespace
    assert role["rules"][0]["apiGroups"] == ["apps"]
    assert role["rules"][0]["resources"] == ["deployments"]
    assert role["rules"][0]["resourceNames"] == [deployment_name]
    assert role["rules"][0]["verbs"] == ["get"]

    assert binding["kind"] == "RoleBinding"
    assert binding["metadata"]["namespace"] == identity.namespace
    assert binding["subjects"][0] == {
        "kind": "ServiceAccount",
        "name": "afterpush-runtime-worker",
        "namespace": "afterpush-system",
    }


def test_preparation_is_deterministic(tmp_path):
    project_id = uuid4()
    arguments = {
        "repository_root": tmp_path,
        "project_id": project_id,
        "application_name": "payment-api",
        "environment": "dev",
    }

    first_paths = prepare_gitops_rbac(**arguments)
    first_contents = [
        path.read_bytes() for path in first_paths
    ]

    second_paths = prepare_gitops_rbac(**arguments)
    second_contents = [
        path.read_bytes() for path in second_paths
    ]

    assert first_paths == second_paths
    assert first_contents == second_contents


@pytest.mark.parametrize(
    "environment,application_name",
    [
        ("production", "payment-api"),
        ("dev", "Payment API"),
        ("dev", "payment_api"),
        ("dev", "../payment-api"),
    ],
)
def test_rejects_invalid_inputs(
    tmp_path,
    environment,
    application_name,
):
    with pytest.raises(ValueError):
        prepare_gitops_rbac(
            repository_root=tmp_path,
            project_id=uuid4(),
            application_name=application_name,
            environment=environment,
        )

    assert not (tmp_path / "gitops").exists()


def test_rejects_non_uuid_project_id(tmp_path):
    with pytest.raises(TypeError):
        prepare_gitops_rbac(
            repository_root=tmp_path,
            project_id="invalid-id",
            application_name="payment-api",
            environment="dev",
        )
