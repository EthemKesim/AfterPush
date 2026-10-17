from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ArgoCDSyncVerification:
    verified: bool
    reason: str


def verify_argocd_sync(
    application: dict[str, Any],
    expected_commit_sha: str,
) -> ArgoCDSyncVerification:
    """
    Verify that ArgoCD reports a successful sync of the
    expected Git commit for both configured sources.

    This is conservative: newer commits are not accepted
    without additional configuration verification.

    A successful sync does not independently prove
    Kubernetes rollout completion.
    """

    if (
        not isinstance(expected_commit_sha, str)
        or len(expected_commit_sha) != 40
        or any(
            character not in "0123456789abcdefABCDEF"
            for character in expected_commit_sha
        )
    ):
        raise ValueError("Invalid expected Git commit SHA")

    if not isinstance(application, dict):
        return ArgoCDSyncVerification(False, "invalid_application")

    status = application.get("status")

    if not isinstance(status, dict):
        return ArgoCDSyncVerification(False, "missing_status")

    sync = status.get("sync")

    if not isinstance(sync, dict):
        return ArgoCDSyncVerification(False, "missing_sync_status")

    if sync.get("status") != "Synced":
        return ArgoCDSyncVerification(False, "not_synced")

    operation_state = status.get("operationState")

    if not isinstance(operation_state, dict):
        return ArgoCDSyncVerification(False, "missing_operation_state")

    if operation_state.get("phase") != "Succeeded":
        return ArgoCDSyncVerification(False, "sync_not_successful")

    sync_result = operation_state.get("syncResult")

    if not isinstance(sync_result, dict):
        return ArgoCDSyncVerification(False, "missing_sync_result")

    revisions = sync_result.get("revisions")

    if (
        not isinstance(revisions, list)
        or len(revisions) != 2
        or not all(isinstance(value, str) for value in revisions)
    ):
        return ArgoCDSyncVerification(False, "invalid_sync_revisions")

    expected = expected_commit_sha.lower()

    if any(revision.lower() != expected for revision in revisions):
        return ArgoCDSyncVerification(False, "revision_mismatch")

    current_revisions = sync.get("revisions")

    if (
        not isinstance(current_revisions, list)
        or len(current_revisions) != 2
        or not all(isinstance(value, str) for value in current_revisions)
    ):
        return ArgoCDSyncVerification(False, "invalid_current_revisions")

    if any(revision.lower() != expected for revision in current_revisions):
        return ArgoCDSyncVerification(False, "current_revision_mismatch")

    return ArgoCDSyncVerification(True, "verified")
