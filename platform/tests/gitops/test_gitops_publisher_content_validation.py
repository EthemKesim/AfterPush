import subprocess

import pytest

from afterpush_api.services.gitops_publisher import (
    GitOpsPublishError,
    publish_gitops_file,
)

from afterpush_api.services.namespace_bootstrap import (
    render_namespace_bootstrap,
)
from uuid import UUID


PROJECT_ID = "12471cf9-11d4-4089-ad0d-2c4b777fc227"


def git(root, *args):
    result = subprocess.run(
        ["git", "-C", str(root), *args],
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout.strip()


@pytest.fixture
def repository(tmp_path):
    root = tmp_path / "repo"
    root.mkdir()

    git(root, "init")
    git(root, "config", "user.name", "AfterPush Test")
    git(root, "config", "user.email", "test@example.com")

    (root / "README.md").write_text("initial\n")
    git(root, "add", "README.md")
    git(root, "commit", "-m", "initial")

    return root


def create_manifest(repository):
    target = (
        repository
        / f"gitops/platform/namespaces/dev/{PROJECT_ID}/namespace.yaml"
    )

    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        render_namespace_bootstrap(
            project_id=UUID(PROJECT_ID),
            application_name="payment-api",
            environment="dev",
        ),
        encoding="utf-8",
    )

    return target


def test_invalid_content_never_commits(repository):
    manifest = create_manifest(repository)
    original_head = git(repository, "rev-parse", "HEAD")

    def reject_content(path):
        raise ValueError("Invalid namespace security policy")

    with pytest.raises(
        GitOpsPublishError,
        match="content validation failed",
    ):
        publish_gitops_file(
            repository_root=repository,
            values_path=manifest,
            commit_message="unsafe bootstrap",
            validate_content=reject_content,
        )

    assert git(repository, "rev-parse", "HEAD") == original_head
    assert git(repository, "diff", "--cached", "--name-only") == ""


def test_validated_content_can_commit(repository):
    manifest = create_manifest(repository)
    called = []

    def accept_content(path):
        called.append(path)

    commit_sha = publish_gitops_file(
        repository_root=repository,
        values_path=manifest,
        commit_message="validated bootstrap",
        validate_content=accept_content,
    )

    assert commit_sha == git(repository, "rev-parse", "HEAD")
    assert called == [manifest]


def test_validation_runs_before_git_staging(repository):
    manifest = create_manifest(repository)

    def check_index(path):
        assert git(repository, "diff", "--cached", "--name-only") == ""

    publish_gitops_file(
        repository_root=repository,
        values_path=manifest,
        commit_message="validated bootstrap",
        validate_content=check_index,
    )



def test_namespace_publication_requires_validation(repository):
    manifest = create_manifest(repository)

    commit_sha = publish_gitops_file(
        repository_root=repository,
        values_path=manifest,
        commit_message="validated namespace",
    )

    assert commit_sha == git(repository, "rev-parse", "HEAD")


def test_deployment_publication_remains_compatible(repository):
    target = (
        repository
        / f"gitops/apps/dev/{PROJECT_ID}/payment-api/values.yaml"
    )

    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("image:\\n  tag: test\\n")

    commit_sha = publish_gitops_file(
        repository_root=repository,
        values_path=target,
        commit_message="deployment publication",
    )

    assert commit_sha == git(repository, "rev-parse", "HEAD")
