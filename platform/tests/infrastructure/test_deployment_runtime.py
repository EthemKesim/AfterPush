import pytest

from afterpush_api.services.argocd_observation import ArgoCDObservation
from afterpush_api.services.kubernetes_rollout import KubernetesRolloutObservation
from afterpush_api.services.deployment_runtime import (
    evaluate_deployment_runtime,
)


def make_argocd(sync="Synced", health="Healthy"):
    return ArgoCDObservation(
        sync_status=sync,
        health_status=health,
        source_revisions=("abc123", "abc123"),
    )


def make_kubernetes(complete=True, revision=5):
    return KubernetesRolloutObservation(
        observed_revision=revision,
        desired_replicas=2,
        updated_replicas=2,
        ready_replicas=2,
        available_replicas=2,
        rollout_complete=complete,
    )


def evaluate(argocd=None, kubernetes=None, **kwargs):
    return evaluate_deployment_runtime(
        argocd if argocd is not None else make_argocd(),
        kubernetes if kubernetes is not None else make_kubernetes(),
        expected_revision=5,
        **kwargs,
    )


def test_healthy_requires_gitops_verification():
    result = evaluate()

    assert result.status == "unverified"
    assert result.revision_verified is False


def test_healthy_when_all_checks_pass():
    result = evaluate(gitops_revision_verified=True)

    assert result.status == "healthy"
    assert result.rollout_complete is True
    assert result.revision_verified is True


def test_out_of_sync_is_not_healthy():
    result = evaluate(
        argocd=make_argocd(sync="OutOfSync"),
        gitops_revision_verified=True,
    )

    assert result.status == "out_of_sync"


def test_degraded_application():
    result = evaluate(
        argocd=make_argocd(health="Degraded"),
        gitops_revision_verified=True,
    )

    assert result.status == "degraded"


def test_progressing_application():
    result = evaluate(
        argocd=make_argocd(health="Progressing"),
        gitops_revision_verified=True,
    )

    assert result.status == "progressing"


def test_unknown_sync_status_is_unverified():
    result = evaluate(
        argocd=make_argocd(sync="Unknown"),
        gitops_revision_verified=True,
    )

    assert result.status == "unverified"


def test_incomplete_rollout_is_not_healthy():
    result = evaluate(
        kubernetes=make_kubernetes(complete=False),
        gitops_revision_verified=True,
    )

    assert result.status == "progressing"
    assert result.rollout_complete is False


def test_revision_mismatch_is_not_healthy():
    result = evaluate(
        kubernetes=make_kubernetes(
            complete=False,
            revision=4,
        ),
        gitops_revision_verified=True,
    )

    assert result.status == "revision_mismatch"


def test_missing_revision_is_unverified():
    result = evaluate(
        kubernetes=make_kubernetes(
            complete=False,
            revision=None,
        ),
        gitops_revision_verified=True,
    )

    assert result.status == "unverified"
    assert result.rollout_complete is False
    assert result.revision_verified is False


def test_wrong_revision_without_gitops_verification():
    result = evaluate(
        kubernetes=make_kubernetes(
            complete=False,
            revision=6,
        ),
    )

    assert result.status == "revision_mismatch"
    assert result.revision_verified is False


@pytest.mark.parametrize("value", [None, 1, "true"])
def test_rejects_invalid_verification_value(value):
    with pytest.raises(
        ValueError,
        match="Invalid GitOps verification result",
    ):
        evaluate(gitops_revision_verified=value)


@pytest.mark.parametrize("revision", [0, -1, "5", True])
def test_rejects_invalid_expected_revision(revision):
    with pytest.raises(
        ValueError,
        match="Invalid expected revision",
    ):
        evaluate_deployment_runtime(
            make_argocd(),
            make_kubernetes(),
            expected_revision=revision,
        )
