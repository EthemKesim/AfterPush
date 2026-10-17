"""Non-interactive Git credentials for GitOps workers."""

import os
from urllib.parse import urlsplit


class GitOpsCredentialsError(ValueError):
    """Raised when GitOps authentication is unsafe or incomplete."""


_CREDENTIAL_HELPER = (
    '!f() { if [ "$1" = get ]; then '
    'printf "%s\\n" "username=$AFTERPUSH_GITOPS_USERNAME" '
    '"password=$AFTERPUSH_GITOPS_TOKEN"; fi; }; f'
)


def validate_repository_url(repository_url: str) -> None:
    """Reject HTTP(S) URLs that embed credentials.

    Credentials in a URL can appear in process listings, Git configuration,
    and error output. Workers receive credentials separately from a mounted
    Kubernetes Secret instead.
    """

    parsed = urlsplit(repository_url)

    if parsed.scheme in {"http", "https"} and (
        parsed.username is not None or parsed.password is not None
    ):
        raise GitOpsCredentialsError(
            "GitOps repository URL must not contain credentials."
        )


def git_environment() -> dict[str, str]:
    """Return Git environment with an optional credential helper.

    When both credential variables are absent, local paths and public
    repositories work without modification. When configured, Git obtains the
    username and token only when it requests credentials; the token is never
    placed in the repository URL or a Git command argument.
    """

    environment = os.environ.copy()
    username = environment.get("AFTERPUSH_GITOPS_USERNAME", "").strip()
    token = environment.get("AFTERPUSH_GITOPS_TOKEN", "").strip()

    if not username and not token:
        return environment

    if not username or not token:
        raise GitOpsCredentialsError(
            "Both AFTERPUSH_GITOPS_USERNAME and "
            "AFTERPUSH_GITOPS_TOKEN are required."
        )

    if "\n" in username or "\r" in username or "\n" in token or "\r" in token:
        raise GitOpsCredentialsError(
            "GitOps credentials must not contain line breaks."
        )

    try:
        existing_count = int(environment.get("GIT_CONFIG_COUNT", "0"))
    except ValueError as exc:
        raise GitOpsCredentialsError(
            "GIT_CONFIG_COUNT must be an integer."
        ) from exc

    if existing_count < 0:
        raise GitOpsCredentialsError(
            "GIT_CONFIG_COUNT cannot be negative."
        )

    environment["GIT_CONFIG_COUNT"] = str(existing_count + 1)
    environment[f"GIT_CONFIG_KEY_{existing_count}"] = "credential.helper"
    environment[f"GIT_CONFIG_VALUE_{existing_count}"] = _CREDENTIAL_HELPER

    return environment
