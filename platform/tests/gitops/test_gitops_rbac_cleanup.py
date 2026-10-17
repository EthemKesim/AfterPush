from uuid import uuid4

from afterpush_api.services.gitops_rbac_cleanup import (
    find_orphaned_rbac,
)
from afterpush_api.services.gitops_rbac_selection import (
    RBACPublicationTarget,
)


def create_rbac_directory(root, target, extra_file=False):
    directory = (
        root
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

    if extra_file:
        (directory / "unexpected.yaml").write_text(
            "kind: ConfigMap\n",
            encoding="utf-8",
        )

    return directory


def test_valid_rbac_is_not_cleanup_candidate(tmp_path):
    target = RBACPublicationTarget(
        project_id=uuid4(),
        application_name="backend",
        environment="dev",
    )
    directory = create_rbac_directory(tmp_path, target)

    candidates = find_orphaned_rbac(
        repository_root=tmp_path,
        valid_targets={target},
    )

    assert candidates == []
    assert directory.is_dir()


def test_orphaned_rbac_is_reported_without_deletion(tmp_path):
    target = RBACPublicationTarget(
        project_id=uuid4(),
        application_name="payment-api",
        environment="prod",
    )
    directory = create_rbac_directory(tmp_path, target)

    candidates = find_orphaned_rbac(
        repository_root=tmp_path,
        valid_targets=set(),
    )

    assert len(candidates) == 1
    assert candidates[0].target == target
    assert candidates[0].relative_directory == (
        directory.relative_to(tmp_path)
    )

    assert directory.is_dir()
    assert (directory / "argocd-rbac.yaml").is_file()
    assert (directory / "deployment-rbac.yaml").is_file()


def test_unexpected_files_are_not_cleanup_candidates(tmp_path):
    target = RBACPublicationTarget(
        project_id=uuid4(),
        application_name="backend",
        environment="staging",
    )
    directory = create_rbac_directory(
        tmp_path,
        target,
        extra_file=True,
    )

    candidates = find_orphaned_rbac(
        repository_root=tmp_path,
        valid_targets=set(),
    )

    assert candidates == []
    assert (directory / "unexpected.yaml").is_file()


def test_missing_rbac_root_returns_no_candidates(tmp_path):
    assert find_orphaned_rbac(
        repository_root=tmp_path,
        valid_targets=set(),
    ) == []
