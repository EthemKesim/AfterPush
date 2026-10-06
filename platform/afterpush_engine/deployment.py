from pathlib import Path

import yaml

from afterpush_engine.pipeline import build_helm_values


def prepare_deployment(
    config_path: Path,
    gitops_root: Path,
) -> Path:
    values = build_helm_values(config_path)

    application_name = values["application"]["name"]

    application_directory = gitops_root / application_name
    application_directory.mkdir(
        parents=True,
        exist_ok=True,
    )

    values_path = application_directory / "values.yaml"

    if values_path.exists():
        raise FileExistsError(
            f"GitOps deployment already exists: {values_path}"
        )

    values_path.write_text(
        yaml.safe_dump(
            values,
            sort_keys=False,
        ),
        encoding="utf-8",
    )

    return values_path