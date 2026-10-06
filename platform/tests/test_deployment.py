from pathlib import Path

import yaml

import pytest

from afterpush_engine.deployment import (
    GitOpsRootNotFoundError,
    find_gitops_root,
    prepare_deployment,
)

EXAMPLE_PATH = (
    Path(__file__).resolve().parents[1]
    / "examples"
    / "afterpush.yaml"
)


def test_prepare_deployment_creates_gitops_values(tmp_path: Path):
    config_path = (
        Path(__file__).resolve().parents[1]
        / "examples"
        / "afterpush.yaml"
    )

    values_path = prepare_deployment(
        config_path=config_path,
        gitops_root=tmp_path,
    )

    assert values_path == tmp_path / "afterpush-api" / "values.yaml"
    assert values_path.exists()

    values = yaml.safe_load(
        values_path.read_text(encoding="utf-8")
    )

    assert values["application"]["name"] == "afterpush-api"
    assert values["image"]["repository"] == "afterpush-api"
    assert values["service"]["targetPort"] == 3000
    assert values["ingress"]["host"] == "afterpush.local"
    assert values["autoscaling"]["enabled"] is True
    assert values["monitoring"]["enabled"] is True


def test_prepare_deployment_refuses_to_overwrite_existing_values(
    tmp_path: Path,
):
    config_path = (
        Path(__file__).resolve().parents[1]
        / "examples"
        / "afterpush.yaml"
    )

    application_directory = tmp_path / "afterpush-api"
    application_directory.mkdir()

    values_path = application_directory / "values.yaml"
    values_path.write_text(
        "existing: true\n",
        encoding="utf-8",
    )

    try:
        prepare_deployment(
            config_path=config_path,
            gitops_root=tmp_path,
        )
    except FileExistsError:
        pass
    else:
        raise AssertionError(
            "prepare_deployment should refuse to overwrite existing values"
        )

    assert values_path.read_text(encoding="utf-8") == "existing: true\n"

def test_find_gitops_root_from_nested_directory(tmp_path: Path):
    repository_root = tmp_path / "AfterPush"
    gitops_root = repository_root / "gitops" / "apps"
    nested_directory = repository_root / "platform" / "somewhere"

    gitops_root.mkdir(parents=True)
    nested_directory.mkdir(parents=True)

    result = find_gitops_root(nested_directory)

    assert result == gitops_root

def test_find_gitops_root_raises_clear_error_when_missing(
    tmp_path: Path,
):
    with pytest.raises(
        GitOpsRootNotFoundError,
        match="Could not find gitops/apps",
    ):
        find_gitops_root(tmp_path)


def test_prepare_deployment_updates_existing_values_when_allowed(
    tmp_path: Path,
):
    gitops_root = tmp_path / "gitops" / "apps"

    values_path = (
        gitops_root
        / "afterpush-api"
        / "values.yaml"
    )

    values_path.parent.mkdir(parents=True)

    values_path.write_text(
        "old: value\n",
        encoding="utf-8",
    )

    result = prepare_deployment(
        config_path=EXAMPLE_PATH,
        gitops_root=gitops_root,
        allow_update=True,
    )

    assert result == values_path

    values = yaml.safe_load(
        values_path.read_text(encoding="utf-8")
    )

    assert values["application"]["name"] == "afterpush-api"
    assert values["image"]["repository"] == "afterpush-api"
    assert "old" not in values
