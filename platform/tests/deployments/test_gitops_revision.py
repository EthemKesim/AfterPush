import pytest

from afterpush_api.services.gitops_revision import (
    StaleGitOpsRevisionError,
    apply_deployment_revision,
)


def test_initial_revision_is_added():
    values = {
        "image": {"repository": "example/api", "tag": "v1"},
        "replicaCount": 2,
    }

    result = apply_deployment_revision(values, revision=1)

    assert result["deployment"]["revision"] == 1
    assert result["image"] == values["image"]
    assert result["replicaCount"] == 2


def test_newer_revision_is_accepted():
    values = {
        "deployment": {"revision": 11},
        "image": {"tag": "v11"},
    }

    result = apply_deployment_revision(values, revision=12)

    assert result["deployment"]["revision"] == 12


def test_older_revision_is_rejected():
    values = {
        "deployment": {"revision": 12},
        "image": {"tag": "v12"},
    }

    with pytest.raises(StaleGitOpsRevisionError):
        apply_deployment_revision(values, revision=11)


def test_same_revision_preserves_existing_settings():
    values = {
        "deployment": {"revision": 12, "source": "afterpush"},
        "image": {"repository": "example/api", "tag": "v12"},
        "replicaCount": 3,
    }

    result = apply_deployment_revision(values, revision=12)

    assert result == values


def test_invalid_revision_is_rejected():
    with pytest.raises(ValueError):
        apply_deployment_revision({"image": {}}, revision=0)

    with pytest.raises(ValueError):
        apply_deployment_revision({"image": {}}, revision=True)
