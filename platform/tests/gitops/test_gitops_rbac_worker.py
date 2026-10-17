import json
import sys
from types import SimpleNamespace
from uuid import uuid4

from afterpush_api.workers import gitops_rbac_reconciliation


def test_worker_reports_success(monkeypatch, capsys):
    calls = []

    class FakeSession:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc_value, traceback):
            return False

    def fake_reconcile(**kwargs):
        calls.append(kwargs)
        return SimpleNamespace(
            processed=3,
            succeeded=3,
            failed=0,
            failed_targets=[],
        )

    monkeypatch.setenv(
        "AFTERPUSH_GITOPS_REPOSITORY_URL",
        "https://example.com/gitops.git",
    )
    monkeypatch.setattr(
        sys,
        "argv",
        ["gitops_rbac_reconciliation", "--batch-size", "2"],
    )
    monkeypatch.setattr(
        gitops_rbac_reconciliation,
        "SessionLocal",
        FakeSession,
    )
    monkeypatch.setattr(
        gitops_rbac_reconciliation,
        "reconcile_published_rbac",
        fake_reconcile,
    )

    exit_code = gitops_rbac_reconciliation.main()
    output = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert output["processed"] == 3
    assert output["succeeded"] == 3
    assert output["failed"] == 0
    assert len(calls) == 1
    assert calls[0]["batch_size"] == 2


def test_worker_reports_failed_targets(monkeypatch, capsys):
    target = SimpleNamespace(
        project_id=uuid4(),
        application_name="backend",
        environment="dev",
    )

    class FakeSession:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc_value, traceback):
            return False

    monkeypatch.setenv(
        "AFTERPUSH_GITOPS_REPOSITORY_URL",
        "https://example.com/gitops.git",
    )
    monkeypatch.setattr(
        sys,
        "argv",
        ["gitops_rbac_reconciliation"],
    )
    monkeypatch.setattr(
        gitops_rbac_reconciliation,
        "SessionLocal",
        FakeSession,
    )
    monkeypatch.setattr(
        gitops_rbac_reconciliation,
        "reconcile_published_rbac",
        lambda **kwargs: SimpleNamespace(
            processed=2,
            succeeded=1,
            failed=1,
            failed_targets=[target],
        ),
    )

    exit_code = gitops_rbac_reconciliation.main()
    output = json.loads(capsys.readouterr().out)

    assert exit_code == 1
    assert output["processed"] == 2
    assert output["succeeded"] == 1
    assert output["failed"] == 1
    assert output["failed_targets"] == [
        {
            "project_id": str(target.project_id),
            "application_name": "backend",
            "environment": "dev",
        }
    ]
