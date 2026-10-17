
from uuid import UUID

import pytest
import yaml

from afterpush_api.services.bootstrap import (
    GitOpsBootstrapError,
    bootstrap_gitops_application,
    build_resource_name,
)


PROJECT_A = UUID("123e4567-e89b-12d3-a456-426614174000")
PROJECT_B = UUID("123e4567-e89b-12d3-a456-426614174001")


def test_bootstrap_creates_values_file(tmp_path):
    values_path = bootstrap_gitops_application(
        gitops_root=tmp_path,
        application_name="payment-service",
        environment="staging",
        image_repository="nginx",
        image_tag="v1.0.0",
        port=3000,
        replicas=2,
    )

    assert values_path.is_file()

    values = yaml.safe_load(
        values_path.read_text(encoding="utf-8")
    )

    assert values["application"]["name"] == "payment-service"
    assert "resourceName" not in values["application"]
    assert values["environment"]["name"] == "staging"
    assert values["image"]["repository"] == "nginx"
    assert values["image"]["tag"] == "v1.0.0"
    assert values["service"]["targetPort"] == 3000
    assert values["replicaCount"] == 2
    assert values["autoscaling"]["enabled"] is False


def test_bootstrap_does_not_overwrite_existing_values(tmp_path):
    arguments = {
        "gitops_root": tmp_path,
        "application_name": "payment-service",
        "environment": "staging",
        "image_repository": "nginx",
        "image_tag": "v1.0.0",
        "port": 3000,
        "replicas": 2,
    }

    values_path = bootstrap_gitops_application(**arguments)
    original_content = values_path.read_text(encoding="utf-8")

    with pytest.raises(GitOpsBootstrapError):
        bootstrap_gitops_application(
            **{
                **arguments,
                "image_tag": "v2.0.0",
            }
        )

    assert values_path.read_text(encoding="utf-8") == original_content


@pytest.mark.parametrize(
    "port",
    [0, -1, 65536],
)
def test_bootstrap_rejects_invalid_port(tmp_path, port):
    with pytest.raises(GitOpsBootstrapError):
        bootstrap_gitops_application(
            gitops_root=tmp_path,
            application_name="payment-service",
            environment="staging",
            image_repository="nginx",
            image_tag="v1.0.0",
            port=port,
            replicas=2,
        )


def test_bootstrap_rejects_invalid_replicas(tmp_path):
    with pytest.raises(GitOpsBootstrapError):
        bootstrap_gitops_application(
            gitops_root=tmp_path,
            application_name="payment-service",
            environment="staging",
            image_repository="nginx",
            image_tag="v1.0.0",
            port=3000,
            replicas=0,
        )


def test_bootstrap_separates_environments(tmp_path):
    common_arguments = {
        "gitops_root": tmp_path,
        "application_name": "payment-service",
        "image_repository": "nginx",
        "image_tag": "v1.0.0",
        "port": 3000,
        "replicas": 2,
    }

    dev_path = bootstrap_gitops_application(
        **common_arguments,
        environment="dev",
    )

    staging_path = bootstrap_gitops_application(
        **common_arguments,
        environment="staging",
    )

    assert dev_path != staging_path
    assert dev_path.is_file()
    assert staging_path.is_file()


def test_resource_name_is_stable():
    first = build_resource_name("backend-api", PROJECT_A)
    second = build_resource_name("backend-api", PROJECT_A)

    assert first == second


def test_resource_names_differ_between_projects():
    first = build_resource_name("backend-api", PROJECT_A)
    second = build_resource_name("backend-api", PROJECT_B)

    assert first != second


def test_resource_names_differ_between_applications():
    first = build_resource_name("backend-api", PROJECT_A)
    second = build_resource_name("backend-worker", PROJECT_A)

    assert first != second


def test_resource_names_differ_for_similar_long_names():
    first = build_resource_name(
        "backend-service-for-customer-orders",
        PROJECT_A,
    )
    second = build_resource_name(
        "backend-service-for-customer-payments",
        PROJECT_A,
    )

    assert first != second


@pytest.mark.parametrize(
    "application_name",
    [
        "backend",
        "backend-api",
        "a" * 100,
    ],
)
def test_resource_name_is_valid_and_short(application_name):
    resource_name = build_resource_name(
        application_name,
        PROJECT_A,
    )

    assert len(resource_name) <= 45
    assert resource_name[0].isalnum()
    assert resource_name[-1].isalnum()
    assert all(
        character.islower()
        or character.isdigit()
        or character == "-"
        for character in resource_name
    )


def test_bootstrap_writes_project_resource_name(tmp_path):
    values_path = bootstrap_gitops_application(
        gitops_root=tmp_path,
        application_name="backend-api",
        environment="staging",
        image_repository="nginx",
        image_tag="v1.0.0",
        port=3000,
        replicas=2,
        project_id=PROJECT_A,
    )

    values = yaml.safe_load(
        values_path.read_text(encoding="utf-8")
    )

    assert values["application"]["name"] == "backend-api"
    assert values["application"]["resourceName"] == build_resource_name(
        "backend-api",
        PROJECT_A,
    )
    assert str(PROJECT_A) in str(values_path)


def test_legacy_bootstrap_remains_compatible(tmp_path):
    values_path = bootstrap_gitops_application(
        gitops_root=tmp_path,
        application_name="backend-api",
        environment="dev",
        image_repository="nginx",
        image_tag="v1",
        port=3000,
        replicas=1,
    )

    values = yaml.safe_load(
        values_path.read_text(encoding="utf-8")
    )

    assert values["application"]["name"] == "backend-api"
    assert "resourceName" not in values["application"]
