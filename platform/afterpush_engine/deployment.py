from pathlib import Path

import yaml

from afterpush_engine.pipeline import build_helm_values

class GitOpsRootNotFoundError(Exception):
    """Raised when the GitOps applications directory cannot be discovered."""

def find_gitops_root(start_path: Path) -> Path:
    current_path = start_path.resolve()

    for directory in (current_path, *current_path.parents):
        gitops_root = directory / "gitops" / "apps"

        if gitops_root.is_dir():
            return gitops_root

    raise GitOpsRootNotFoundError(
    "Could not find gitops/apps from the current directory "
    "or any parent directory."
)


def prepare_deployment(
    config_path: Path,
    gitops_root: Path,
    allow_update: bool = False,
) -> Path:
    values = build_helm_values(config_path)

    application_name = values["application"]["name"]

    application_directory = gitops_root / application_name
    application_directory.mkdir(
        parents=True,
        exist_ok=True,
    )

    values_path = application_directory / "values.yaml"

    if values_path.exists() and not allow_update:
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