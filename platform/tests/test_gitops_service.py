
import copy

import pytest
import yaml

from afterpush_api.services.gitops import (
    GitOpsError,
    GitOpsValuesNotFoundError,
    InvalidGitOpsPathError,
    get_values_path,
    prepare_gitops_values,
)


@pytest.fixture
def gitops_root(tmp_path):
    values_directory = (
        tmp_path
        / "apps"
        / "staging"
        / "payment-service"
    )
    values_directory.mkdir(parents=True)

    values = {
        "application": {
            "name": "payment-service",
        },
        "image": {
            "repository": "nginx",
            "tag": "v1.0.0",
            "pullPolicy": "IfNotPresent",
        },
        "service": {
            "type": "ClusterIP",
            "port": 80,
            "targetPort": 3000,
        },
        "ingress": {
            "enabled": True,
            "host": "payment.example.com",
        },
        "monitoring": {
            "enabled": True,
        },
    }

    values_path = values_directory / "values.yaml"
    values_path.write_text(
        yaml.safe_dump(values),
        encoding="utf-8",
    )

    return tmp_path


def test_get_values_path(gitops_root):
    result = get_values_path(
        gitops_root,
        "payment-service",
        "staging",
    )

    assert result == (
        gitops_root
        / "apps"
        / "staging"
        / "payment-service"
        / "values.yaml"
    )


def test_prepare_gitops_values_updates_image(gitops_root):
    result = prepare_gitops_values(
        gitops_root=gitops_root,
        application_name="payment-service",
        environment="staging",
        image_repository="myregistry/payment-service",
        image_tag="v1.1.0",
    )

    assert result["image"]["repository"] == (
        "myregistry/payment-service"
    )
    assert result["image"]["tag"] == "v1.1.0"


def test_prepare_gitops_values_preserves_settings(gitops_root):
    result = prepare_gitops_values(
        gitops_root,
        "payment-service",
        "staging",
        "myregistry/payment-service",
        "v1.1.0",
    )

    assert result["image"]["pullPolicy"] == "IfNotPresent"
    assert result["service"]["targetPort"] == 3000
    assert result["ingress"]["enabled"] is True
    assert result["monitoring"]["enabled"] is True


def test_prepare_gitops_values_does_not_modify_file(gitops_root):
    values_path = get_values_path(
        gitops_root,
        "payment-service",
        "staging",
    )

    original_content = values_path.read_text(encoding="utf-8")

    prepare_gitops_values(
        gitops_root,
        "payment-service",
        "staging",
        "nginx",
        "v2.0.0",
    )

    assert values_path.read_text(encoding="utf-8") == original_content


def test_missing_values_file_raises_error(tmp_path):
    with pytest.raises(GitOpsValuesNotFoundError):
        prepare_gitops_values(
            tmp_path,
            "missing-app",
            "staging",
            "nginx",
            "v1.0.0",
        )


@pytest.mark.parametrize(
    "invalid_name",
    [
        "../production",
        "../../secret",
        "/etc/passwd",
        "Payment Service",
        "payment_service",
        "",
    ],
)
def test_invalid_application_name(tmp_path, invalid_name):
    with pytest.raises(InvalidGitOpsPathError):
        get_values_path(
            tmp_path,
            invalid_name,
            "staging",
        )


@pytest.mark.parametrize(
    "invalid_environment",
    [
        "../production",
        "../../secret",
        "/tmp",
        "Staging Environment",
        "",
    ],
)
def test_invalid_environment(tmp_path, invalid_environment):
    with pytest.raises(InvalidGitOpsPathError):
        get_values_path(
            tmp_path,
            "payment-service",
            invalid_environment,
        )


def test_invalid_yaml_mapping(tmp_path):
    values_directory = (
        tmp_path / "apps" / "staging" / "payment-service"
    )
    values_directory.mkdir(parents=True)

    (values_directory / "values.yaml").write_text(
        "- item1\n- item2\n",
        encoding="utf-8",
    )

    with pytest.raises(GitOpsError):
        prepare_gitops_values(
            tmp_path,
            "payment-service",
            "staging",
            "nginx",
            "v1.0.0",
        )


def test_missing_image_mapping(tmp_path):
    values_directory = (
        tmp_path / "apps" / "staging" / "payment-service"
    )
    values_directory.mkdir(parents=True)

    (values_directory / "values.yaml").write_text(
        "application:\n  name: payment-service\n",
        encoding="utf-8",
    )

    with pytest.raises(GitOpsError):
        prepare_gitops_values(
            tmp_path,
            "payment-service",
            "staging",
            "nginx",
            "v1.0.0",
        )
