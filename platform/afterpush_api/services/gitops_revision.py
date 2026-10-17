from afterpush_api.services.gitops import GitOpsError


class StaleGitOpsRevisionError(GitOpsError):
    """A newer deployment revision is already published."""


def apply_deployment_revision(
    values: dict,
    revision: int,
) -> dict:
    """
    Add deployment revision metadata to Helm values.

    Reject revisions older than the one already present.
    """

    if not isinstance(revision, int) or isinstance(revision, bool) or revision < 1:
        raise ValueError("Deployment revision must be a positive integer.")

    if not isinstance(values, dict):
        raise GitOpsError("Helm values must be a mapping.")

    deployment = values.get("deployment", {})

    if not isinstance(deployment, dict):
        raise GitOpsError("Deployment metadata must be a mapping.")

    current_revision = deployment.get("revision", 0)

    if (
        not isinstance(current_revision, int)
        or isinstance(current_revision, bool)
        or current_revision < 0
    ):
        raise GitOpsError("Existing deployment revision is invalid.")

    if revision < current_revision:
        raise StaleGitOpsRevisionError(
            f"Revision {revision} is older than "
            f"published revision {current_revision}."
        )

    return {
        **values,
        "deployment": {
            **deployment,
            "revision": revision,
        },
    }
