from unittest.mock import Mock, patch

import pytest

from afterpush_api.workers.namespace_bootstrap import main


MODULE = "afterpush_api.workers.namespace_bootstrap"


def test_dry_run_does_not_create_kubernetes_client(capsys):
    db = Mock()
    db_context = Mock()
    db_context.__enter__ = Mock(return_value=db)
    db_context.__exit__ = Mock(return_value=False)

    with (
        patch(f"{MODULE}.SessionLocal", return_value=db_context),
        patch(
            f"{MODULE}.get_pending_deployment_ids",
            return_value=["deployment-1", "deployment-2"],
        ),
        patch(f"{MODULE}.create_bootstrap_core_api") as core_api,
        patch(f"{MODULE}.reconcile_pending_namespace_bootstraps") as reconcile,
    ):
        result = main(["--limit", "2"])

    assert result == 0
    assert '"mode": "dry-run"' in capsys.readouterr().out
    core_api.assert_not_called()
    reconcile.assert_not_called()


def test_execute_requires_repository_url(monkeypatch):
    monkeypatch.delenv(
        "AFTERPUSH_GITOPS_REPOSITORY_URL",
        raising=False,
    )

    with patch(f"{MODULE}.create_bootstrap_core_api") as core_api:
        result = main(["--execute"])

    assert result == 2
    core_api.assert_not_called()


def test_execute_calls_bootstrap_worker(monkeypatch):
    monkeypatch.setenv(
        "AFTERPUSH_GITOPS_REPOSITORY_URL",
        "test-repository",
    )

    db = Mock()
    db_context = Mock()
    db_context.__enter__ = Mock(return_value=db)
    db_context.__exit__ = Mock(return_value=False)

    results = {
        "ready": 1,
        "waiting": 2,
        "skipped": 0,
        "errors": 0,
    }

    with (
        patch(f"{MODULE}.SessionLocal", return_value=db_context),
        patch(
            f"{MODULE}.create_bootstrap_core_api",
            return_value=object(),
        ),
        patch(
            f"{MODULE}.reconcile_pending_namespace_bootstraps",
            return_value=results,
        ) as reconcile,
    ):
        result = main(["--execute", "--limit", "3"])

    assert result == 0
    reconcile.assert_called_once()


def test_execute_returns_error_when_worker_reports_errors(monkeypatch):
    monkeypatch.setenv(
        "AFTERPUSH_GITOPS_REPOSITORY_URL",
        "test-repository",
    )

    db = Mock()
    db_context = Mock()
    db_context.__enter__ = Mock(return_value=db)
    db_context.__exit__ = Mock(return_value=False)

    with (
        patch(f"{MODULE}.SessionLocal", return_value=db_context),
        patch(
            f"{MODULE}.create_bootstrap_core_api",
            return_value=object(),
        ),
        patch(
            f"{MODULE}.reconcile_pending_namespace_bootstraps",
            return_value={
                "ready": 0,
                "waiting": 0,
                "skipped": 0,
                "errors": 1,
            },
        ),
    ):
        result = main(["--execute"])

    assert result == 1


@pytest.mark.parametrize("limit", [0, -1])
def test_rejects_invalid_limit(limit):
    with pytest.raises(SystemExit) as exc:
        main(["--limit", str(limit)])

    assert exc.value.code == 2
