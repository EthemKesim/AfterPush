from copy import deepcopy

import pytest

from afterpush_api.services.argocd_sync_verification import (
    verify_argocd_sync,
)


SHA = "a" * 40
OTHER_SHA = "b" * 40


def make_application():
    return {
        "status": {
            "sync": {
                "status": "Synced",
                "revisions": [SHA, SHA],
            },
            "operationState": {
                "phase": "Succeeded",
                "syncResult": {
                    "revisions": [SHA, SHA],
                },
            },
        },
    }


def test_successful_sync_is_verified():
    result = verify_argocd_sync(make_application(), SHA)

    assert result.verified is True
    assert result.reason == "verified"


def test_sha_comparison_is_case_insensitive():
    result = verify_argocd_sync(make_application(), SHA.upper())

    assert result.verified is True


@pytest.mark.parametrize("sha", [
    "",
    "abc123",
    "g" * 40,
    None,
    123,
])
def test_invalid_expected_sha_is_rejected(sha):
    with pytest.raises(ValueError, match="Invalid expected Git commit SHA"):
        verify_argocd_sync(make_application(), sha)


def test_invalid_application_is_rejected():
    result = verify_argocd_sync(None, SHA)

    assert result.verified is False
    assert result.reason == "invalid_application"


def test_missing_status_is_rejected():
    result = verify_argocd_sync({}, SHA)

    assert result.reason == "missing_status"


def test_missing_sync_status_is_rejected():
    result = verify_argocd_sync({"status": {}}, SHA)

    assert result.reason == "missing_sync_status"


def test_out_of_sync_is_rejected():
    application = make_application()
    application["status"]["sync"]["status"] = "OutOfSync"

    result = verify_argocd_sync(application, SHA)

    assert result.verified is False
    assert result.reason == "not_synced"


def test_missing_operation_state_is_rejected():
    application = make_application()
    del application["status"]["operationState"]

    result = verify_argocd_sync(application, SHA)

    assert result.reason == "missing_operation_state"


@pytest.mark.parametrize("phase", [
    "Failed",
    "Running",
    "Error",
    None,
])
def test_unsuccessful_operation_is_rejected(phase):
    application = make_application()
    application["status"]["operationState"]["phase"] = phase

    result = verify_argocd_sync(application, SHA)

    assert result.verified is False
    assert result.reason == "sync_not_successful"


def test_missing_sync_result_is_rejected():
    application = make_application()
    del application["status"]["operationState"]["syncResult"]

    result = verify_argocd_sync(application, SHA)

    assert result.reason == "missing_sync_result"


@pytest.mark.parametrize("revisions", [
    [],
    [SHA],
    [SHA, SHA, SHA],
    [SHA, 123],
    None,
])
def test_invalid_sync_revisions_are_rejected(revisions):
    application = make_application()
    application["status"]["operationState"]["syncResult"]["revisions"] = revisions

    result = verify_argocd_sync(application, SHA)

    assert result.verified is False
    assert result.reason == "invalid_sync_revisions"


def test_different_synced_revision_is_rejected():
    application = make_application()
    application["status"]["operationState"]["syncResult"]["revisions"] = [
        SHA,
        OTHER_SHA,
    ]

    result = verify_argocd_sync(application, SHA)

    assert result.reason == "revision_mismatch"


@pytest.mark.parametrize("revisions", [
    [],
    [SHA],
    [SHA, SHA, SHA],
    [SHA, None],
    None,
])
def test_invalid_current_revisions_are_rejected(revisions):
    application = make_application()
    application["status"]["sync"]["revisions"] = revisions

    result = verify_argocd_sync(application, SHA)

    assert result.verified is False
    assert result.reason == "invalid_current_revisions"


def test_current_revision_mismatch_is_rejected():
    application = make_application()
    application["status"]["sync"]["revisions"] = [
        SHA,
        OTHER_SHA,
    ]

    result = verify_argocd_sync(application, SHA)

    assert result.verified is False
    assert result.reason == "current_revision_mismatch"


def test_verification_does_not_modify_application():
    application = make_application()
    original = deepcopy(application)

    verify_argocd_sync(application, SHA)

    assert application == original
