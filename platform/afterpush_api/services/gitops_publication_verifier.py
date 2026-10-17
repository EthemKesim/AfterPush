from dataclasses import dataclass
from pathlib import Path

import yaml

from afterpush_api.services.deployment_gitops import DeploymentGitOpsSpec
from afterpush_api.services.gitops import get_values_path
from afterpush_api.services.gitops_publisher import run_git
from afterpush_api.services.gitops_workspace import isolated_gitops_workspace


@dataclass(frozen=True)
class GitOpsPublicationVerification:
    matches: bool
    commit_sha: str | None
    observed_revision: int | None


def verify_gitops_publication(
    repository_url: str,
    spec: DeploymentGitOpsSpec,
) -> GitOpsPublicationVerification:
    """
    Read the current GitOps main branch and verify a deployment.

    This function does not create commits or push changes.
    """

    with isolated_gitops_workspace(
        repository_url=repository_url,
        branch="main",
    ) as workspace:
        values_path = get_values_path(
            gitops_root=Path(workspace) / "gitops",
            application_name=spec.application_name,
            environment=spec.environment,
            project_id=spec.project_id,
        )

        if not values_path.is_file():
            return GitOpsPublicationVerification(
                matches=False,
                commit_sha=None,
                observed_revision=None,
            )

        with values_path.open("r", encoding="utf-8") as file:
            values = yaml.safe_load(file)

        if not isinstance(values, dict):
            return GitOpsPublicationVerification(
                matches=False,
                commit_sha=None,
                observed_revision=None,
            )

        deployment = values.get("deployment", {})
        image = values.get("image", {})
        service = values.get("service", {})
        autoscaling = values.get("autoscaling", {})

        if not all(
            isinstance(section, dict)
            for section in (deployment, image, service, autoscaling)
        ):
            return GitOpsPublicationVerification(
                matches=False,
                commit_sha=None,
                observed_revision=None,
            )

        observed_revision = deployment.get("revision")

        matches = (
            type(observed_revision) is int
            and observed_revision == spec.revision
            and image.get("repository") == spec.image_repository
            and image.get("tag") == spec.image_tag
            and service.get("targetPort") == spec.port
            and (
                values.get("replicaCount") == spec.replicas
                or autoscaling.get("enabled") is True
            )
        )

        return GitOpsPublicationVerification(
            matches=matches,
            commit_sha=(
                run_git(workspace, "rev-parse", "HEAD")
                if matches
                else None
            ),
            observed_revision=(
                observed_revision
                if type(observed_revision) is int
                else None
            ),
        )
