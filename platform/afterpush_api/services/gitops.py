
import os
import re
import tempfile
from pathlib import Path
from uuid import UUID

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

MAX_KUBERNETES_NAMESPACE_LENGTH = 63
PROJECT_NAMESPACE_PREFIX = "ap-"
PROJECT_ID_LENGTH = 36

MAX_PROJECT_ENVIRONMENT_LENGTH = (
    MAX_KUBERNETES_NAMESPACE_LENGTH
    - len(PROJECT_NAMESPACE_PREFIX)
    - 1
    - PROJECT_ID_LENGTH
)


def validate_name(name: str) -> None:
    if (
        not isinstance(name, str)
        or not SAFE_NAME_PATTERN.fullmatch(name)
    ):
        raise InvalidGitOpsPathError(
            f"Invalid GitOps application or environment name: {name}"
        )


def validate_project_id(project_id: UUID | None) -> None:
    if project_id is not None and not isinstance(project_id, UUID):
        raise InvalidGitOpsPathError(
            "GitOps project_id must be a UUID."
        )


def validate_project_environment(
    environment: str,
    project_id: UUID | None,
) -> None:
    """
    Ensure project-aware environments produce valid
    Kubernetes namespace names.
    """

    validate_name(environment)
    validate_project_id(project_id)

    if project_id is None:
        return

    namespace = f"{PROJECT_NAMESPACE_PREFIX}{environment}-{project_id}"

    if len(namespace) > MAX_KUBERNETES_NAMESPACE_LENGTH:
        raise InvalidGitOpsPathError(
            "Project environment name is too long. "
            f"Maximum length is {MAX_PROJECT_ENVIRONMENT_LENGTH} "
            "characters."
        )


def get_values_path(
    gitops_root: Path,
    application_name: str,
    environment: str,
    project_id: UUID | None = None,
) -> Path:
    """
    Return a safe GitOps values path.

    When project_id is supplied, isolate the application
    under its project's UUID directory.

    Reject symlinks within the managed GitOps path.
    """

    validate_name(application_name)
    validate_project_environment(environment, project_id)

    root = Path(gitops_root)
    apps_directory = root / "apps"
    environment_directory = apps_directory / environment

    if project_id is None:
        application_directory = (
            environment_directory / application_name
        )
        managed_paths = (
            apps_directory,
            environment_directory,
            application_directory,
        )
    else:
        project_directory = (
            environment_directory / str(project_id)
        )
        application_directory = (
            project_directory / application_name
        )
        managed_paths = (
            apps_directory,
            environment_directory,
            project_directory,
            application_directory,
        )

    values_path = application_directory / "values.yaml"

    if root.is_symlink():
        raise InvalidGitOpsPathError(
            f"GitOps root cannot be a symlink: {root}"
        )

    for path in (*managed_paths, values_path):
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
    project_id: UUID | None = None,
) -> dict:
    """
    Prepare updated Helm values without modifying files.
    """

    values_path = get_values_path(
        gitops_root,
        application_name,
        environment,
        project_id=project_id,
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
    project_id: UUID | None = None,
) -> Path:
    """
    Atomically replace an existing Helm values file.
    """

    values_path = get_values_path(
        gitops_root,
        application_name,
        environment,
        project_id=project_id,
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

        get_values_path(
            gitops_root,
            application_name,
            environment,
            project_id=project_id,
        )

        os.replace(temporary_path, values_path)

    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)

    return values_path
