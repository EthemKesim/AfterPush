from uuid import UUID

import pytest

from afterpush_api.services.argocd_identity import (
    build_argocd_application_identity,
)


PROJECT_A = UUID("123e4567-e89b-12d3-a456-426614174000")
PROJECT_B = UUID("123e4567-e89b-12d3-a456-426614174001")


def test_builds_expected_application_identity():
    identity = build_argocd_application_identity(
        project_id=PROJECT_A,
        application_name="backend-api",
        environment="staging",
    )

    assert identity.application_name == "ap-staging-4bbe9136ed80"
    assert identity.namespace == f"ap-staging-{PROJECT_A}"
    assert identity.gitops_path == (
        f"gitops/apps/staging/{PROJECT_A}/backend-api"
    )


def test_identity_is_deterministic():
    first = build_argocd_application_identity(
        PROJECT_A, "backend-api", "staging"
    )
    second = build_argocd_application_identity(
        PROJECT_A, "backend-api", "staging"
    )

    assert first == second


def test_different_projects_have_distinct_identities():
    first = build_argocd_application_identity(
        PROJECT_A, "backend-api", "staging"
    )
    second = build_argocd_application_identity(
        PROJECT_B, "backend-api", "staging"
    )

    assert first.application_name != second.application_name
    assert first.namespace != second.namespace


def test_different_environments_have_distinct_identities():
    dev = build_argocd_application_identity(
        PROJECT_A, "backend-api", "dev"
    )
    staging = build_argocd_application_identity(
        PROJECT_A, "backend-api", "staging"
    )

    assert dev.application_name != staging.application_name
    assert dev.namespace != staging.namespace


@pytest.mark.parametrize("environment", ["", "production", "../prod"])
def test_rejects_invalid_environment(environment):
    with pytest.raises(ValueError, match="Unsupported deployment environment"):
        build_argocd_application_identity(
            PROJECT_A, "backend-api", environment
        )


def test_rejects_empty_application_name():
    with pytest.raises(ValueError, match="Invalid application name"):
        build_argocd_application_identity(
            PROJECT_A, "", "staging"
        )


@pytest.mark.parametrize(
    "application_name",
    [
        "../backend",
        "Backend_API",
        "backend/api",
        "backend api",
        "-backend",
        "backend-",
        "ab",
        "a" * 101,
    ],
)
def test_rejects_invalid_application_names(application_name):
    with pytest.raises(ValueError, match="Invalid application name"):
        build_argocd_application_identity(
            project_id=PROJECT_A,
            application_name=application_name,
            environment="staging",
        )
