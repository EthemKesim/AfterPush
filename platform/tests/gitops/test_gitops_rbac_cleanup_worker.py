import json
from contextlib import contextmanager
from pathlib import Path
from uuid import uuid4

from afterpush_api.services.gitops_rbac_cleanup import (
    RBACCleanupCandidate,
)
from afterpush_api.services.gitops_rbac_cleanup_dry_run import (
    RBACCleanupDryRunResult,
)
from afterpush_api.services.gitops_rbac_selection import (
    RBACPublicationTarget,
)
from afterpush_api.workers import gitops_rbac_cleanup


def test_cleanup_worker_returns_dry_run_json(
    monkeypatch,
    tmp_path,
    capsys,
):
    monkeypatch.setenv(
        "AFTERPUSH_GITOPS_REPOSITORY_URL",
        "local-test-repository",
    )

    target = RBACPublicationTarget(
        project_id=uuid4(),
        application_name="old-backend",
        environment="dev",
    )

    directory = (
        Path("gitops/platform/rbac/projects")
        / "dev"
        / str(target.project_id)
        / target.application_name
    )

    @contextmanager
    def fake_workspace(repository_url):
        assert repository_url == "local-test-repository"
        yield tmp_path

    @contextmanager
    def fake_session():
        yield object()

    def fake_plan(*, db, repository_root, batch_size):
        assert repository_root == tmp_path
        assert batch_size == 10

        return RBACCleanupDryRunResult(
            valid_target_count=5,
            orphaned_candidates=(
                RBACCleanupCandidate(
                    target=target,
                    relative_directory=directory,
                ),
            ),
        )

    monkeypatch.setattr(
        gitops_rbac_cleanup,
        "isolated_gitops_workspace",
        fake_workspace,
    )
    monkeypatch.setattr(
        gitops_rbac_cleanup,
        "SessionLocal",
        fake_session,
    )
    monkeypatch.setattr(
        gitops_rbac_cleanup,
        "plan_rbac_cleanup",
        fake_plan,
    )

    exit_code = gitops_rbac_cleanup.main(
        ["--batch-size", "10"]
    )

    assert exit_code == 0

    report = json.loads(capsys.readouterr().out)

    assert report["mode"] == "dry-run"
    assert report["valid_target_count"] == 5
    assert report["orphaned_count"] == 1
    assert report["orphaned_directories"] == [str(directory)]


def test_cleanup_worker_requires_repository_url(
    monkeypatch,
    capsys,
):
    monkeypatch.delenv(
        "AFTERPUSH_GITOPS_REPOSITORY_URL",
        raising=False,
    )

    exit_code = gitops_rbac_cleanup.main([])

    assert exit_code == 2
    assert "AFTERPUSH_GITOPS_REPOSITORY_URL" in (
        capsys.readouterr().err
    )


def test_cleanup_worker_returns_failure_on_workspace_error(
    monkeypatch,
):
    monkeypatch.setenv(
        "AFTERPUSH_GITOPS_REPOSITORY_URL",
        "local-test-repository",
    )

    @contextmanager
    def failing_workspace(repository_url):
        raise RuntimeError("Simulated GitOps failure")
        yield

    monkeypatch.setattr(
        gitops_rbac_cleanup,
        "isolated_gitops_workspace",
        failing_workspace,
    )

    assert gitops_rbac_cleanup.main([]) == 1
