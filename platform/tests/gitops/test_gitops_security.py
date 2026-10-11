
import pytest
import yaml

from afterpush_api.services.gitops import (
    InvalidGitOpsPathError,
    get_values_path,
    prepare_gitops_values,
    write_gitops_values,
)
from afterpush_api.services.sync import sync_gitops_application


def test_rejects_symlinked_application_directory(tmp_path):
    gitops_root = tmp_path / "gitops"
    outside = tmp_path / "outside"

    outside.mkdir()
    application_parent = gitops_root / "apps" / "staging"
    application_parent.mkdir(parents=True)

    (application_parent / "payment-service").symlink_to(
        outside,
        target_is_directory=True,
    )

    with pytest.raises(InvalidGitOpsPathError):
        get_values_path(
            gitops_root,
            "payment-service",
            "staging",
        )


def test_rejects_symlinked_values_file(tmp_path):
    gitops_root = tmp_path / "gitops"
    outside_file = tmp_path / "outside.yaml"

    outside_file.write_text(
        "image:\n  tag: original\n",
        encoding="utf-8",
    )

    application_directory = (
        gitops_root / "apps" / "staging" / "payment-service"
    )
    application_directory.mkdir(parents=True)

    (application_directory / "values.yaml").symlink_to(
        outside_file
    )

    with pytest.raises(InvalidGitOpsPathError):
        prepare_gitops_values(
            gitops_root,
            "payment-service",
            "staging",
            "nginx",
            "v2.0.0",
        )

    assert "original" in outside_file.read_text(
        encoding="utf-8"
    )


def test_rejects_symlinked_environment_directory(tmp_path):
    gitops_root = tmp_path / "gitops"
    outside = tmp_path / "outside"

    outside.mkdir()
    (gitops_root / "apps").mkdir(parents=True)

    (gitops_root / "apps" / "staging").symlink_to(
        outside,
        target_is_directory=True,
    )

    with pytest.raises(InvalidGitOpsPathError):
        get_values_path(
            gitops_root,
            "payment-service",
            "staging",
        )


def test_rejects_symlinked_apps_directory(tmp_path):
    gitops_root = tmp_path / "gitops"
    outside = tmp_path / "outside"

    outside.mkdir()
    gitops_root.mkdir()

    (gitops_root / "apps").symlink_to(
        outside,
        target_is_directory=True,
    )

    with pytest.raises(InvalidGitOpsPathError):
        get_values_path(
            gitops_root,
            "payment-service",
            "staging",
        )


def test_sync_does_not_write_through_symlink(tmp_path):
    gitops_root = tmp_path / "gitops"
    outside_file = tmp_path / "outside.yaml"

    original_values = {
        "image": {
            "repository": "nginx",
            "tag": "original",
        }
    }

    outside_file.write_text(
        yaml.safe_dump(original_values),
        encoding="utf-8",
    )

    application_directory = (
        gitops_root / "apps" / "staging" / "payment-service"
    )
    application_directory.mkdir(parents=True)

    (application_directory / "values.yaml").symlink_to(
        outside_file
    )

    with pytest.raises(InvalidGitOpsPathError):
        sync_gitops_application(
            gitops_root=gitops_root,
            application_name="payment-service",
            environment="staging",
            image_repository="nginx",
            image_tag="v9.0.0",
            port=3000,
            replicas=2,
        )

    saved_values = yaml.safe_load(
        outside_file.read_text(encoding="utf-8")
    )

    assert saved_values["image"]["tag"] == "original"


def test_rejects_symlinked_gitops_root(tmp_path):
    actual_root = tmp_path / "actual-gitops"
    actual_root.mkdir()

    linked_root = tmp_path / "linked-gitops"
    linked_root.symlink_to(
        actual_root,
        target_is_directory=True,
    )

    with pytest.raises(InvalidGitOpsPathError):
        get_values_path(
            linked_root,
            "payment-service",
            "staging",
        )
