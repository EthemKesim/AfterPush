from uuid import uuid4

import pytest

from afterpush_api.services import gitops_rbac_cleanup_dry_run
from afterpush_api.services.gitops_rbac_cleanup_dry_run import (
    plan_rbac_cleanup,
)
from afterpush_api.services.gitops_rbac_selection import (
    RBACPublicationTarget,
)


def create_rbac_directory(repository_root, target):
    directory = (
        repository_root
        / "gitops/platform/rbac/projects"
        / target.environment
        / str(target.project_id)
        / target.application_name
    )
    directory.mkdir(parents=True)

    (directory / "argocd-rbac.yaml").write_text(
        "kind: Role\n",
        encoding="utf-8",
    )
    (directory / "deployment-rbac.yaml").write_text(
        "kind: RoleBinding\n",
        encoding="utf-8",
    )

    return directory


def test_dry_run_reports_only_orphaned_rbac(
    tmp_path,
    monkeypatch,
):
    project_id = uuid4()

    valid_target = RBACPublicationTarget(
        project_id=project_id,
        application_name="backend",
        environment="dev",
    )
    orphaned_target = RBACPublicationTarget(
        project_id=project_id,
        application_name="old-backend",
        environment="dev",
    )

    valid_directory = create_rbac_directory(
        tmp_path,
        valid_target,
    )
    orphaned_directory = create_rbac_directory(
        tmp_path,
        orphaned_target,
    )

    def fake_snapshot(db, batch_size=100):
        assert batch_size == 10
        return {valid_target}

    monkeypatch.setattr(
        gitops_rbac_cleanup_dry_run,
        "collect_rbac_cleanup_protection_snapshot",
        fake_snapshot,
    )

    result = plan_rbac_cleanup(
        db=object(),
        repository_root=tmp_path,
        batch_size=10,
    )

    assert result.valid_target_count == 1
    assert len(result.orphaned_candidates) == 1
    assert result.orphaned_candidates[0].target == orphaned_target

    assert valid_directory.is_dir()
    assert orphaned_directory.is_dir()


def test_dry_run_stops_if_snapshot_fails(
    tmp_path,
    monkeypatch,
):
    def failing_snapshot(db, batch_size=100):
        raise RuntimeError("Database snapshot failed")

    monkeypatch.setattr(
        gitops_rbac_cleanup_dry_run,
        "collect_rbac_cleanup_protection_snapshot",
        failing_snapshot,
    )

    with pytest.raises(
        RuntimeError,
        match="Database snapshot failed",
    ):
        plan_rbac_cleanup(
            db=object(),
            repository_root=tmp_path,
        )
