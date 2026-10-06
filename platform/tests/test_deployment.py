from pathlib import Path

import yaml

from afterpush_engine.deployment import prepare_deployment


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