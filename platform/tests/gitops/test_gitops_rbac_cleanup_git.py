import subprocess
from pathlib import Path
from uuid import uuid4

from afterpush_api.services.gitops_rbac_cleanup import (
    RBACCleanupCandidate,
)
from afterpush_api.services.gitops_rbac_cleanup_git import (
    verify_tracked_rbac_candidate,
)
from afterpush_api.services.gitops_rbac_selection import (
    RBACPublicationTarget,
)


def run_git(repository, *args):
    return subprocess.run(
        ["git", "-C", str(repository), *args],
        check=True,
        capture_output=True,
        text=True,
    )


def create_candidate(repository):
    target = RBACPublicationTarget(
        project_id=uuid4(),
        application_name="backend",
        environment="dev",
    )

    relative_directory = (
        Path("gitops/platform/rbac/projects")
        / target.environment
        / str(target.project_id)
        / target.application_name
    )

    directory = repository / relative_directory
    directory.mkdir(parents=True)

    (directory / "argocd-rbac.yaml").write_text(
        "kind: Role\n",
        encoding="utf-8",
    )
    (directory / "deployment-rbac.yaml").write_text(
        "kind: RoleBinding\n",
        encoding="utf-8",
    )

    return RBACCleanupCandidate(
        target=target,
        relative_directory=relative_directory,
    )


def test_tracked_rbac_candidate_is_accepted(tmp_path):
    run_git(tmp_path, "init", "-q")

    candidate = create_candidate(tmp_path)

    run_git(
        tmp_path,
        "add",
        "--",
        str(candidate.relative_directory),
    )

    run_git(tmp_path, "-c", "user.name=AfterPush Test",
            "-c", "user.email=test@afterpush.local",
            "commit", "-qm", "Add RBAC manifests")

    assert verify_tracked_rbac_candidate(
        repository_root=tmp_path,
        candidate=candidate,
    )


def test_untracked_rbac_candidate_is_rejected(tmp_path):
    run_git(tmp_path, "init", "-q")

    candidate = create_candidate(tmp_path)

    assert not verify_tracked_rbac_candidate(
        repository_root=tmp_path,
        candidate=candidate,
    )


def test_unexpected_candidate_path_is_rejected(tmp_path):
    run_git(tmp_path, "init", "-q")

    candidate = create_candidate(tmp_path)

    invalid_candidate = RBACCleanupCandidate(
        target=candidate.target,
        relative_directory=Path("unrelated/backend"),
    )

    assert not verify_tracked_rbac_candidate(
        repository_root=tmp_path,
        candidate=invalid_candidate,
    )


def test_staged_but_uncommitted_rbac_is_rejected(tmp_path):
    run_git(tmp_path, "init", "-q")

    candidate = create_candidate(tmp_path)

    run_git(
        tmp_path,
        "add",
        "--",
        str(candidate.relative_directory),
    )

    # Both files are staged, but HEAD does not contain them.
    assert not verify_tracked_rbac_candidate(
        repository_root=tmp_path,
        candidate=candidate,
    )


def test_head_rbac_remains_valid_after_unrelated_commit(tmp_path):
    run_git(tmp_path, "init", "-q")

    candidate = create_candidate(tmp_path)

    run_git(
        tmp_path,
        "add",
        "--",
        str(candidate.relative_directory),
    )

    run_git(
        tmp_path,
        "-c", "user.name=AfterPush Test",
        "-c", "user.email=test@afterpush.local",
        "commit", "-qm", "Add RBAC manifests",
    )

    (tmp_path / "README.md").write_text(
        "# Test repository\n",
        encoding="utf-8",
    )

    run_git(tmp_path, "add", "README.md")
    run_git(
        tmp_path,
        "-c", "user.name=AfterPush Test",
        "-c", "user.email=test@afterpush.local",
        "commit", "-qm", "Update README",
    )

    assert verify_tracked_rbac_candidate(
        repository_root=tmp_path,
        candidate=candidate,
    )


def commit_rbac_candidate(repository):
    run_git(repository, "init", "-q")

    candidate = create_candidate(repository)

    run_git(
        repository,
        "add",
        "--",
        str(candidate.relative_directory),
    )

    run_git(
        repository,
        "-c", "user.name=AfterPush Test",
        "-c", "user.email=test@afterpush.local",
        "commit", "-qm", "Add RBAC manifests",
    )

    return candidate


def test_unstaged_rbac_modification_is_rejected(tmp_path):
    candidate = commit_rbac_candidate(tmp_path)

    manifest = (
        tmp_path
        / candidate.relative_directory
        / "deployment-rbac.yaml"
    )

    manifest.write_text(
        manifest.read_text() + "# Modified after commit\n"
    )

    assert not verify_tracked_rbac_candidate(
        repository_root=tmp_path,
        candidate=candidate,
    )


def test_staged_rbac_modification_is_rejected(tmp_path):
    candidate = commit_rbac_candidate(tmp_path)

    manifest = (
        tmp_path
        / candidate.relative_directory
        / "argocd-rbac.yaml"
    )

    manifest.write_text(
        manifest.read_text() + "# Staged modification\n"
    )

    run_git(
        tmp_path,
        "add",
        "--",
        str(candidate.relative_directory),
    )

    assert not verify_tracked_rbac_candidate(
        repository_root=tmp_path,
        candidate=candidate,
    )


def test_unrelated_file_modification_is_allowed(tmp_path):
    candidate = commit_rbac_candidate(tmp_path)

    (tmp_path / "README.md").write_text(
        "Unrelated local change\n"
    )

    assert verify_tracked_rbac_candidate(
        repository_root=tmp_path,
        candidate=candidate,
    )


def test_git_symlink_manifest_is_rejected(tmp_path):
    candidate = commit_rbac_candidate(tmp_path)

    manifest = (
        tmp_path
        / candidate.relative_directory
        / "deployment-rbac.yaml"
    )

    manifest.unlink()
    manifest.symlink_to("argocd-rbac.yaml")

    run_git(tmp_path, "add", "--", str(candidate.relative_directory))
    run_git(
        tmp_path,
        "-c", "user.name=AfterPush Test",
        "-c", "user.email=test@afterpush.local",
        "commit", "-qm", "Replace manifest with symlink",
    )

    assert not verify_tracked_rbac_candidate(
        repository_root=tmp_path,
        candidate=candidate,
    )


def test_executable_git_manifest_is_rejected(tmp_path):
    candidate = commit_rbac_candidate(tmp_path)

    manifest = (
        tmp_path
        / candidate.relative_directory
        / "deployment-rbac.yaml"
    )

    manifest.chmod(0o755)

    run_git(tmp_path, "add", "--", str(candidate.relative_directory))
    run_git(
        tmp_path,
        "-c", "user.name=AfterPush Test",
        "-c", "user.email=test@afterpush.local",
        "commit", "-qm", "Make manifest executable",
    )

    assert not verify_tracked_rbac_candidate(
        repository_root=tmp_path,
        candidate=candidate,
    )


def test_regular_git_manifests_are_accepted(tmp_path):
    candidate = commit_rbac_candidate(tmp_path)

    for filename in ("argocd-rbac.yaml", "deployment-rbac.yaml"):
        result = run_git(
            tmp_path,
            "ls-tree",
            "HEAD",
            "--",
            str(candidate.relative_directory / filename),
        )

        assert result.stdout.startswith("100644 blob ")

    assert verify_tracked_rbac_candidate(
        repository_root=tmp_path,
        candidate=candidate,
    )
