
import pytest
import yaml

from afterpush_api.services.gitops import (
    GitOpsError,
    GitOpsValuesNotFoundError,
    get_values_path,
    prepare_gitops_values,
    write_gitops_values,
)


@pytest.fixture
def gitops_root(tmp_path):
    values_path = (
        tmp_path
        / "apps"
        / "staging"
        / "payment-service"
        / "values.yaml"
    )

    values_path.parent.mkdir(parents=True)

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

    values_path.write_text(
        yaml.safe_dump(values, sort_keys=False),
        encoding="utf-8",
    )

    return tmp_path


def test_write_updates_image_tag(gitops_root):
    updated_values = prepare_gitops_values(
        gitops_root,
        "payment-service",
        "staging",
        "nginx",
        "v1.1.0",
    )

    values_path = write_gitops_values(
        gitops_root,
        "payment-service",
        "staging",
        updated_values,
    )

    saved_values = yaml.safe_load(
        values_path.read_text(encoding="utf-8")
    )

    assert saved_values["image"]["tag"] == "v1.1.0"


def test_write_preserves_other_settings(gitops_root):
    updated_values = prepare_gitops_values(
        gitops_root,
        "payment-service",
        "staging",
        "myregistry/payment-service",
        "v2.0.0",
    )

    values_path = write_gitops_values(
        gitops_root,
        "payment-service",
        "staging",
        updated_values,
    )

    saved_values = yaml.safe_load(
        values_path.read_text(encoding="utf-8")
    )

    assert saved_values["image"]["repository"] == (
        "myregistry/payment-service"
    )
    assert saved_values["image"]["pullPolicy"] == "IfNotPresent"
    assert saved_values["service"]["targetPort"] == 3000
    assert saved_values["ingress"]["enabled"] is True
    assert saved_values["monitoring"]["enabled"] is True


def test_write_missing_file_raises_error(tmp_path):
    with pytest.raises(GitOpsValuesNotFoundError):
        write_gitops_values(
            tmp_path,
            "missing-app",
            "staging",
            {"image": {"tag": "v1.0.0"}},
        )


def test_invalid_values_do_not_modify_file(gitops_root):
    values_path = get_values_path(
        gitops_root,
        "payment-service",
        "staging",
    )

    original_content = values_path.read_text(encoding="utf-8")

    with pytest.raises(GitOpsError):
        write_gitops_values(
            gitops_root,
            "payment-service",
            "staging",
            {"application": {"name": "payment-service"}},
        )

    assert values_path.read_text(encoding="utf-8") == original_content


def test_write_leaves_no_temporary_files(gitops_root):
    updated_values = prepare_gitops_values(
        gitops_root,
        "payment-service",
        "staging",
        "nginx",
        "v3.0.0",
    )

    values_path = write_gitops_values(
        gitops_root,
        "payment-service",
        "staging",
        updated_values,
    )

    temporary_files = list(
        values_path.parent.glob(".values-*.tmp")
    )

    assert temporary_files == []
