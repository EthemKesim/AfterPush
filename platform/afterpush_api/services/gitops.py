
import os
import re
import tempfile
from pathlib import Path

import yaml


class GitOpsError(Exception):
    """Base exception for GitOps operations."""


class GitOpsValuesNotFoundError(GitOpsError):
    """Raised when an application's Helm values file does not exist."""


class InvalidGitOpsPathError(GitOpsError):
    """Raised when a GitOps path is unsafe."""


SAFE_NAME_PATTERN = re.compile(
    r"^[a-z0-9](?:[a-z0-9-]*[a-z0-9])?$"
)


def validate_name(name: str) -> None:
    if (
        not isinstance(name, str)
        or not SAFE_NAME_PATTERN.fullmatch(name)
    ):
        raise InvalidGitOpsPathError(
            f"Invalid GitOps application or environment name: {name}"
        )


def get_values_path(
    gitops_root: Path,
    application_name: str,
    environment: str,
) -> Path:
    """
    Return a safe GitOps values path.

    Reject symlinks within the managed GitOps path.
    """

    validate_name(application_name)
    validate_name(environment)

    root = Path(gitops_root)

    values_path = (
        root
        / "apps"
        / environment
        / application_name
        / "values.yaml"
    )

    managed_paths = (
        root / "apps",
        root / "apps" / environment,
        root / "apps" / environment / application_name,
        values_path,
    )

    if root.is_symlink():
        raise InvalidGitOpsPathError(
            f"GitOps root cannot be a symlink: {root}"
        )

    for path in managed_paths:
        if path.is_symlink():
            raise InvalidGitOpsPathError(
                f"GitOps path cannot contain symlinks: {path}"
            )

    resolved_root = root.resolve()
    resolved_values = values_path.resolve()

    if not resolved_values.is_relative_to(resolved_root):
        raise InvalidGitOpsPathError(
            "GitOps values path escapes the GitOps root."
        )

    return values_path


def prepare_gitops_values(
    gitops_root: Path,
    application_name: str,
    environment: str,
    image_repository: str,
    image_tag: str,
) -> dict:
    """
    Prepare updated Helm values without modifying files.
    """

    values_path = get_values_path(
        gitops_root,
        application_name,
        environment,
    )

    if not values_path.is_file():
        raise GitOpsValuesNotFoundError(
            f"Helm values file not found: {values_path}"
        )

    with values_path.open("r", encoding="utf-8") as file:
        values = yaml.safe_load(file)

    if not isinstance(values, dict):
        raise GitOpsError(
            "Helm values must contain a YAML mapping."
        )

    image = values.get("image")

    if not isinstance(image, dict):
        raise GitOpsError(
            "Helm values must contain an image mapping."
        )

    updated_values = {
        **values,
        "image": {
            **image,
            "repository": image_repository,
            "tag": image_tag,
        },
    }

    return updated_values


def write_gitops_values(
    gitops_root: Path,
    application_name: str,
    environment: str,
    values: dict,
) -> Path:
    """
    Atomically replace an existing Helm values file.
    """

    values_path = get_values_path(
        gitops_root,
        application_name,
        environment,
    )

    if not values_path.is_file():
        raise GitOpsValuesNotFoundError(
            f"Helm values file not found: {values_path}"
        )

    if not isinstance(values, dict):
        raise GitOpsError(
            "Helm values must contain a YAML mapping."
        )

    if not isinstance(values.get("image"), dict):
        raise GitOpsError(
            "Helm values must contain an image mapping."
        )

    temporary_path = None

    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=values_path.parent,
            prefix=".values-",
            suffix=".tmp",
            delete=False,
        ) as temporary_file:
            temporary_path = Path(temporary_file.name)

            yaml.safe_dump(
                values,
                temporary_file,
                sort_keys=False,
            )

            temporary_file.flush()
            os.fsync(temporary_file.fileno())

        # Recheck before replacing the target file.
        get_values_path(
            gitops_root,
            application_name,
            environment,
        )

        os.replace(temporary_path, values_path)

    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)

    return values_path
