
from pathlib import Path

import pytest
import yaml

from afterpush_engine.deployment import (
    GitOpsRootNotFoundError,
    find_gitops_root,
    prepare_deployment,
)


PLATFORM_ROOT = Path(__file__).resolve().parents[2]

EXAMPLE_PATH = PLATFORM_ROOT / "examples" / "afterpush.yaml"


def test_prepare_deployment_creates_gitops_values(tmp_path: Path):
    values_path = prepare_deployment(
        config_path=EXAMPLE_PATH,
        gitops_root=tmp_path,
    )

    assert values_path == tmp_path / "afterpush-api" / "values.yaml"
    assert values_path.exists()

    values = yaml.safe_load(
        values_path.read_text(encoding="utf-8")
    )

    assert values["application"]["name"] == "afterpush-api"
    assert values["image"]["repository"] == "afterpush-api"
    assert values["service"]["targetPort"] == 8000
    assert values["ingress"]["host"] == "afterpush.local"
    assert values["autoscaling"]["enabled"] is True
    assert values["monitoring"]["enabled"] is True


def test_prepare_deployment_refuses_to_overwrite_existing_values(
    tmp_path: Path,
):
    application_directory = tmp_path / "afterpush-api"
    application_directory.mkdir()

    values_path = application_directory / "values.yaml"
    values_path.write_text(
        "existing: true\n",
        encoding="utf-8",
    )

    with pytest.raises(FileExistsError):
        prepare_deployment(
            config_path=EXAMPLE_PATH,
            gitops_root=tmp_path,
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
