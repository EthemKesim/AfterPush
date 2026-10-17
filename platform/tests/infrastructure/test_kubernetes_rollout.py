from copy import deepcopy

import pytest

from afterpush_api.services.kubernetes_rollout import (
    evaluate_kubernetes_rollout,
)


def make_deployment():
    return {
        "metadata": {
            "generation": 8,
            "annotations": {
                "afterpush.dev/revision": "5",
            },
        },
        "spec": {
            "replicas": 2,
            "template": {
                "metadata": {
                    "annotations": {
                        "afterpush.dev/revision": "5",
                    },
                },
            },
        },
        "status": {
            "observedGeneration": 8,
            "replicas": 2,
            "updatedReplicas": 2,
            "readyReplicas": 2,
            "availableReplicas": 2,
        },
    }


def test_complete_rollout():
    result = evaluate_kubernetes_rollout(
        make_deployment(),
        expected_revision=5,
    )

    assert result.observed_revision == 5
    assert result.desired_replicas == 2
    assert result.rollout_complete is True


def test_rejects_different_revision():
    result = evaluate_kubernetes_rollout(
        make_deployment(),
        expected_revision=6,
    )

    assert result.observed_revision == 5
    assert result.rollout_complete is False


@pytest.mark.parametrize(
    "field,value",
    [
        ("observedGeneration", 7),
        ("replicas", 3),
        ("updatedReplicas", 1),
        ("readyReplicas", 1),
        ("availableReplicas", 1),
    ],
)
def test_incomplete_rollout(field, value):
    deployment = make_deployment()
    deployment["status"][field] = value

    result = evaluate_kubernetes_rollout(
        deployment,
        expected_revision=5,
    )

    assert result.rollout_complete is False


def test_missing_revision_annotation():
    deployment = make_deployment()
    deployment["metadata"]["annotations"] = {}

    result = evaluate_kubernetes_rollout(
        deployment,
        expected_revision=5,
    )

    assert result.observed_revision is None
    assert result.rollout_complete is False


def test_invalid_revision_annotation():
    deployment = make_deployment()
    deployment["metadata"]["annotations"] = {
        "afterpush.dev/revision": "not-a-number",
    }

    result = evaluate_kubernetes_rollout(
        deployment,
        expected_revision=5,
    )

    assert result.observed_revision is None
    assert result.rollout_complete is False


def test_missing_replica_status_is_not_complete():
    deployment = make_deployment()
    deployment["status"] = {
        "observedGeneration": 8,
    }

    result = evaluate_kubernetes_rollout(
        deployment,
        expected_revision=5,
    )

    assert result.rollout_complete is False


@pytest.mark.parametrize(
    "field,value",
    [
        ("replicas", -1),
        ("updatedReplicas", -1),
        ("readyReplicas", "2"),
        ("availableReplicas", True),
    ],
)
def test_rejects_invalid_replica_values(field, value):
    deployment = make_deployment()

    if field == "replicas":
        deployment["spec"][field] = value
    else:
        deployment["status"][field] = value

    with pytest.raises(ValueError):
        evaluate_kubernetes_rollout(
            deployment,
            expected_revision=5,
        )


@pytest.mark.parametrize(
    "expected_revision",
    [0, -1, "5", True],
)
def test_rejects_invalid_expected_revision(expected_revision):
    with pytest.raises(ValueError, match="Invalid expected revision"):
        evaluate_kubernetes_rollout(
            make_deployment(),
            expected_revision=expected_revision,
        )


def test_does_not_mutate_deployment():
    deployment = make_deployment()
    original = deepcopy(deployment)

    evaluate_kubernetes_rollout(
        deployment,
        expected_revision=5,
    )

    assert deployment == original



def test_rejects_old_pod_template_revision():
    deployment = make_deployment()
    deployment["spec"]["template"]["metadata"]["annotations"][
        "afterpush.dev/revision"
    ] = "4"

    result = evaluate_kubernetes_rollout(deployment, 5)

    assert result.observed_revision == 5
    assert result.rollout_complete is False


def test_rejects_missing_pod_template_revision():
    deployment = make_deployment()
    deployment["spec"]["template"]["metadata"]["annotations"] = {}

    result = evaluate_kubernetes_rollout(deployment, 5)

    assert result.rollout_complete is False


def test_rejects_missing_pod_template():
    deployment = make_deployment()
    del deployment["spec"]["template"]

    result = evaluate_kubernetes_rollout(deployment, 5)

    assert result.rollout_complete is False


def test_rejects_invalid_pod_template_revision():
    deployment = make_deployment()
    deployment["spec"]["template"]["metadata"]["annotations"][
        "afterpush.dev/revision"
    ] = "invalid"

    result = evaluate_kubernetes_rollout(deployment, 5)

    assert result.rollout_complete is False


def test_rejects_invalid_pod_template_annotations():
    deployment = make_deployment()
    deployment["spec"]["template"]["metadata"]["annotations"] = "invalid"

    with pytest.raises(ValueError, match="Invalid pod template annotations"):
        evaluate_kubernetes_rollout(deployment, 5)
