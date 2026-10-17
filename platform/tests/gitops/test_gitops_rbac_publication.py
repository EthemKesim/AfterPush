import pytest
import subprocess
from pathlib import Path
from uuid import uuid4

from afterpush_api.services.gitops_rbac_publication import (
    publish_rbac_with_retry,
)


def git(*args) -> str:
    result = subprocess.run(
        ["git", *map(str, args)],
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout.strip()


def test_rbac_publication_and_idempotency(tmp_path):
    remote = tmp_path / "remote.git"
    seed = tmp_path / "seed"

    git("init", "--bare", "--initial-branch=main", remote)
    git("clone", remote, seed)

    git("-C", seed, "config", "user.name", "AfterPush Test")
    git(
        "-C", seed, "config",
        "user.email", "test@afterpush.local",
    )

    (seed / "README.md").write_text(
        "# AfterPush Test\n",
        encoding="utf-8",
    )

    git("-C", seed, "add", "README.md")
    git("-C", seed, "commit", "-m", "Initial commit")
    git("-C", seed, "push", "origin", "HEAD:main")

    project_id = uuid4()

    arguments = {
        "repository_url": str(remote),
        "project_id": project_id,
        "application_name": "payment-api",
        "environment": "dev",
    }

    first_sha = publish_rbac_with_retry(**arguments)

    verification = tmp_path / "verification"
    git("clone", "--branch", "main", remote, verification)

    directory = (
        verification
        / "gitops/platform/rbac/projects/dev"
        / str(project_id)
        / "payment-api"
    )

    assert (directory / "argocd-rbac.yaml").is_file()
    assert (directory / "deployment-rbac.yaml").is_file()

    committed_files = git(
        "-C", verification,
        "diff-tree",
        "--no-commit-id",
        "--name-only",
        "-r",
        "HEAD",
    ).splitlines()

    assert sorted(committed_files) == sorted([
        (
            directory / "argocd-rbac.yaml"
        ).relative_to(verification).as_posix(),
        (
            directory / "deployment-rbac.yaml"
        ).relative_to(verification).as_posix(),
    ])

    assert first_sha == git(
        "-C", verification, "rev-parse", "HEAD"
    )

    second_sha = publish_rbac_with_retry(**arguments)

    assert second_sha == first_sha
    assert git(
        "--git-dir", remote,
        "rev-parse", "refs/heads/main"
    ) == first_sha


def test_retries_rbac_publication_after_concurrent_push(
    tmp_path,
    monkeypatch,
):
    from afterpush_api.services import gitops_rbac_publication

    remote = tmp_path / "remote.git"
    seed = tmp_path / "seed"

    git("init", "--bare", "--initial-branch=main", remote)
    git("clone", remote, seed)

    git("-C", seed, "config", "user.name", "AfterPush Test")
    git(
        "-C", seed, "config",
        "user.email", "test@afterpush.local",
    )

    (seed / "README.md").write_text(
        "# AfterPush Test\n",
        encoding="utf-8",
    )

    git("-C", seed, "add", "README.md")
    git("-C", seed, "commit", "-m", "Initial commit")
    git("-C", seed, "push", "origin", "HEAD:main")

    real_push = gitops_rbac_publication.push_gitops_commit
    attempts = []

    def competing_push(workspace):
        attempts.append(workspace)

        if len(attempts) == 1:
            competitor = tmp_path / "competitor"

            git(
                "clone", "--branch", "main",
                remote, competitor,
            )

            git(
                "-C", competitor, "config",
                "user.name", "Competitor",
            )
            git(
                "-C", competitor, "config",
                "user.email", "competitor@afterpush.local",
            )

            (competitor / "competitor.txt").write_text(
                "Concurrent update\n",
                encoding="utf-8",
            )

            git("-C", competitor, "add", "competitor.txt")
            git(
                "-C", competitor, "commit",
                "-m", "Concurrent update",
            )
            git(
                "-C", competitor, "push",
                "origin", "HEAD:main",
            )

        return real_push(workspace)

    monkeypatch.setattr(
        gitops_rbac_publication,
        "push_gitops_commit",
        competing_push,
    )

    project_id = uuid4()

    published_sha = publish_rbac_with_retry(
        repository_url=str(remote),
        project_id=project_id,
        application_name="payment-api",
        environment="dev",
    )

    assert len(attempts) == 2

    verification = tmp_path / "verification"

    git("clone", "--branch", "main", remote, verification)

    assert (verification / "competitor.txt").is_file()

    rbac_directory = (
        verification
        / "gitops/platform/rbac/projects/dev"
        / str(project_id)
        / "payment-api"
    )

    assert (rbac_directory / "argocd-rbac.yaml").is_file()
    assert (rbac_directory / "deployment-rbac.yaml").is_file()

    assert published_sha == git(
        "-C", verification, "rev-parse", "HEAD"
    )


def test_invalid_rbac_cannot_reach_git_publisher(
    tmp_path,
    monkeypatch,
):
    import yaml

    from afterpush_api.services import gitops_rbac_publication
    from afterpush_api.services.gitops_rbac_validator import (
        GitOpsRBACValidationError,
    )

    remote = tmp_path / "remote.git"
    seed = tmp_path / "seed"

    git("init", "--bare", "--initial-branch=main", remote)
    git("clone", remote, seed)

    git("-C", seed, "config", "user.name", "AfterPush Test")
    git(
        "-C", seed, "config",
        "user.email", "test@afterpush.local",
    )

    (seed / "README.md").write_text(
        "# AfterPush Test\n",
        encoding="utf-8",
    )

    git("-C", seed, "add", "README.md")
    git("-C", seed, "commit", "-m", "Initial commit")
    git("-C", seed, "push", "origin", "HEAD:main")

    initial_sha = git(
        "--git-dir", remote,
        "rev-parse", "refs/heads/main",
    )

    real_prepare = gitops_rbac_publication.prepare_gitops_rbac

    def prepare_invalid_rbac(**kwargs):
        paths = real_prepare(**kwargs)

        deployment_path = next(
            path for path in paths
            if path.name == "deployment-rbac.yaml"
        )

        documents = list(
            yaml.safe_load_all(
                deployment_path.read_text(encoding="utf-8")
            )
        )

        documents[0]["rules"][0]["verbs"].append("delete")

        deployment_path.write_text(
            yaml.safe_dump_all(documents, sort_keys=False),
            encoding="utf-8",
        )

        return paths

    def forbidden_publish(**kwargs):
        pytest.fail(
            "Git publisher must not run for invalid RBAC"
        )

    monkeypatch.setattr(
        gitops_rbac_publication,
        "prepare_gitops_rbac",
        prepare_invalid_rbac,
    )

    monkeypatch.setattr(
        gitops_rbac_publication,
        "publish_gitops_rbac_files",
        forbidden_publish,
    )

    with pytest.raises(GitOpsRBACValidationError):
        publish_rbac_with_retry(
            repository_url=str(remote),
            project_id=uuid4(),
            application_name="payment-api",
            environment="dev",
        )

    final_sha = git(
        "--git-dir", remote,
        "rev-parse", "refs/heads/main",
    )

    assert final_sha == initial_sha


def test_rbac_publication_updates_outdated_manifests(tmp_path):
    import yaml

    remote = tmp_path / "remote.git"
    seed = tmp_path / "seed"

    git("init", "--bare", "--initial-branch=main", remote)
    git("clone", remote, seed)

    git("-C", seed, "config", "user.name", "AfterPush Test")
    git(
        "-C", seed, "config",
        "user.email", "test@afterpush.local",
    )

    (seed / "README.md").write_text(
        "# AfterPush Test\n",
        encoding="utf-8",
    )

    git("-C", seed, "add", "README.md")
    git("-C", seed, "commit", "-m", "Initial commit")
    git("-C", seed, "push", "origin", "HEAD:main")

    project_id = uuid4()

    arguments = {
        "repository_url": str(remote),
        "project_id": project_id,
        "application_name": "payment-api",
        "environment": "dev",
    }

    first_sha = publish_rbac_with_retry(**arguments)

    checkout = tmp_path / "checkout"
    git("clone", "--branch", "main", remote, checkout)

    deployment_path = (
        checkout
        / "gitops/platform/rbac/projects/dev"
        / str(project_id)
        / "payment-api"
        / "deployment-rbac.yaml"
    )

    manifests = list(
        yaml.safe_load_all(deployment_path.read_text())
    )

    role = next(
        item for item in manifests if item["kind"] == "Role"
    )
    binding = next(
        item for item in manifests if item["kind"] == "RoleBinding"
    )

    role["metadata"]["name"] = "afterpush-deployment-reader"
    binding["metadata"]["name"] = (
        "afterpush-deployment-reader-binding"
    )
    binding["roleRef"]["name"] = "afterpush-deployment-reader"

    deployment_path.write_text(
        yaml.safe_dump_all(manifests, sort_keys=False),
        encoding="utf-8",
    )

    git("-C", checkout, "add", "gitops")
    git("-C", checkout, "commit", "-m", "Simulate outdated RBAC")
    git("-C", checkout, "push", "origin", "HEAD:main")

    outdated_sha = git(
        "--git-dir", remote,
        "rev-parse", "refs/heads/main",
    )

    assert outdated_sha != first_sha

    updated_sha = publish_rbac_with_retry(**arguments)

    assert updated_sha != outdated_sha

    git("-C", checkout, "pull", "--ff-only")

    updated = list(
        yaml.safe_load_all(deployment_path.read_text())
    )

    updated_role = next(
        item for item in updated if item["kind"] == "Role"
    )
    updated_binding = next(
        item for item in updated if item["kind"] == "RoleBinding"
    )

    assert updated_role["metadata"]["name"] != (
        "afterpush-deployment-reader"
    )

    assert updated_binding["roleRef"]["name"] == (
        updated_role["metadata"]["name"]
    )

    assert updated_sha == git(
        "-C", checkout, "rev-parse", "HEAD"
    )
