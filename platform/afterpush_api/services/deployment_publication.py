from afterpush_api.services.deployment_gitops import (
    DeploymentGitOpsSpec,
    prepare_deployment_gitops,
)
from afterpush_api.services.gitops_publish_coordinator import (
    publish_with_retry,
)


def publish_deployment_gitops(
    repository_url: str,
    spec: DeploymentGitOpsSpec,
    max_attempts: int = 3,
) -> str | None:
    """
    Publish deployment configuration to GitOps main.

    Uses a fresh checkout for each attempt and retries
    non-fast-forward push conflicts.

    Does not modify deployment database status.
    """

    def prepare_values(repository_root):
        return prepare_deployment_gitops(
            repository_root=repository_root,
            spec=spec,
        )

    return publish_with_retry(
        repository_url=repository_url,
        prepare_values=prepare_values,
        commit_message=(
            f"deploy({spec.environment}): "
            f"{spec.application_name} -> {spec.image_tag}"
        ),
        max_attempts=max_attempts,
    )
