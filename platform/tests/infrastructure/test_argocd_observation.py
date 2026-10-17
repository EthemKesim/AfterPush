import pytest

from afterpush_api.services.argocd_observation import (
    parse_argocd_observation,
)


def make_application(
    sync_status="Synced",
    health_status="Healthy",
    revisions=None,
):
    return {
        "status": {
            "sync": {
                "status": sync_status,
                "revisions": (
                    ["abc123", "def456"]
                    if revisions is None
                    else revisions
                ),
            },
            "health": {
                "status": health_status,
            },
        },
    }


def test_parses_multisource_application():
    observation = parse_argocd_observation(
        make_application()
    )

    assert observation.sync_status == "Synced"
    assert observation.health_status == "Healthy"
    assert observation.source_revisions == (
        "abc123",
        "def456",
    )


def test_parses_out_of_sync_and_degraded():
    observation = parse_argocd_observation(
        make_application(
            sync_status="OutOfSync",
            health_status="Degraded",
        )
    )

    assert observation.sync_status == "OutOfSync"
    assert observation.health_status == "Degraded"


def test_parses_single_source_revision():
    application = {
        "status": {
            "sync": {
                "status": "Synced",
                "revision": "abc123",
            },
            "health": {
                "status": "Healthy",
            },
        },
    }

    observation = parse_argocd_observation(application)

    assert observation.source_revisions == ("abc123",)


def test_accepts_missing_revision_information():
    application = {
        "status": {
            "sync": {"status": "Unknown"},
            "health": {"status": "Unknown"},
        },
    }

    observation = parse_argocd_observation(application)

    assert observation.source_revisions == ()


@pytest.mark.parametrize(
    "application",
    [
        {},
        {"status": None},
        {"status": {"sync": {}, "health": None}},
        {"status": {"sync": None, "health": {}}},
    ],
)
def test_rejects_missing_or_invalid_status(application):
    with pytest.raises(ValueError):
        parse_argocd_observation(application)


@pytest.mark.parametrize(
    "sync_status",
    ["Invalid", "", None],
)
def test_rejects_invalid_sync_status(sync_status):
    with pytest.raises(ValueError, match="Unsupported ArgoCD sync status"):
        parse_argocd_observation(
            make_application(sync_status=sync_status)
        )


@pytest.mark.parametrize(
    "health_status",
    ["Running", "", None],
)
def test_rejects_invalid_health_status(health_status):
    with pytest.raises(ValueError, match="Unsupported ArgoCD health status"):
        parse_argocd_observation(
            make_application(health_status=health_status)
        )


@pytest.mark.parametrize(
    "revisions",
    [
        "abc123",
        [123],
        [""],
        ["abc123", None],
    ],
)
def test_rejects_invalid_source_revisions(revisions):
    with pytest.raises(ValueError, match="Invalid ArgoCD source revisions"):
        parse_argocd_observation(
            make_application(revisions=revisions)
        )
