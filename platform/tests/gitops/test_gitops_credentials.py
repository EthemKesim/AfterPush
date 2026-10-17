import pytest

from afterpush_api.services.gitops_credentials import (
    GitOpsCredentialsError,
    git_environment,
    validate_repository_url,
)
from afterpush_api.services.gitops_workspace import isolated_gitops_workspace


def test_git_environment_uses_helper_without_putting_token_in_config_value(
    monkeypatch,
):
    monkeypatch.setenv("AFTERPUSH_GITOPS_USERNAME", "x-access-token")
    monkeypatch.setenv("AFTERPUSH_GITOPS_TOKEN", "secret-token")
    monkeypatch.delenv("GIT_CONFIG_COUNT", raising=False)

    environment = git_environment()

    assert environment["GIT_CONFIG_COUNT"] == "1"
    assert environment["GIT_CONFIG_KEY_0"] == "credential.helper"
    assert "AFTERPUSH_GITOPS_TOKEN" in environment["GIT_CONFIG_VALUE_0"]
    assert "secret-token" not in environment["GIT_CONFIG_VALUE_0"]


def test_git_environment_rejects_partial_credentials(monkeypatch):
    monkeypatch.setenv("AFTERPUSH_GITOPS_USERNAME", "x-access-token")
    monkeypatch.delenv("AFTERPUSH_GITOPS_TOKEN", raising=False)

    with pytest.raises(GitOpsCredentialsError, match="Both"):
        git_environment()


@pytest.mark.parametrize(
    "repository_url",
    [
        "https://token@example.com/org/gitops.git",
        "https://user:token@example.com/org/gitops.git",
    ],
)
def test_rejects_credentials_embedded_in_https_url(repository_url):
    with pytest.raises(GitOpsCredentialsError, match="must not contain"):
        validate_repository_url(repository_url)


def test_workspace_rejects_authenticated_url_before_clone():
    with pytest.raises(GitOpsCredentialsError):
        with isolated_gitops_workspace(
            "https://token@example.com/org/gitops.git"
        ):
            pass
