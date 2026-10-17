
from uuid import uuid4

import pytest

from afterpush_api.services.gitops import (
    InvalidGitOpsPathError,
    get_values_path,
    validate_project_environment,
)


def test_project_environment_accepts_23_characters():
    project_id = uuid4()
    environment = "a" * 23

    validate_project_environment(environment, project_id)

    namespace = f"ap-{environment}-{project_id}"

    assert len(namespace) == 63


def test_project_environment_rejects_24_characters():
    project_id = uuid4()
    environment = "a" * 24

    with pytest.raises(
        InvalidGitOpsPathError,
        match="Maximum length is 23 characters",
    ):
        validate_project_environment(environment, project_id)


def test_legacy_environment_preserves_existing_behavior():
    validate_project_environment("a" * 24, None)


def test_project_gitops_path_rejects_long_environment(tmp_path):
    with pytest.raises(
        InvalidGitOpsPathError,
        match="Maximum length is 23 characters",
    ):
        get_values_path(
            gitops_root=tmp_path / "gitops",
            application_name="backend-api",
            environment="a" * 24,
            project_id=uuid4(),
        )


def test_project_gitops_path_accepts_valid_environment(tmp_path):
    project_id = uuid4()

    path = get_values_path(
        gitops_root=tmp_path / "gitops",
        application_name="backend-api",
        environment="production",
        project_id=project_id,
    )

    assert path == (
        tmp_path
        / "gitops"
        / "apps"
        / "production"
        / str(project_id)
        / "backend-api"
        / "values.yaml"
    )


def test_project_environment_rejects_invalid_characters():
    with pytest.raises(InvalidGitOpsPathError):
        validate_project_environment("Production_Test", uuid4())
