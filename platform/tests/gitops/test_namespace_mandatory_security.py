import subprocess
from uuid import UUID

import pytest
import yaml

from afterpush_api.services.gitops_publisher import (
    GitOpsPublishError,
    publish_gitops_file,
)
from afterpush_api.services.namespace_bootstrap import (
    render_namespace_bootstrap,
)


PROJECT_ID = UUID("12471cf9-11d4-4089-ad0d-2c4b777fc227")


def git(root, *args):
    return subprocess.run(
        ["git", "-C", str(root), *args],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


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
            project_id=PROJECT_ID,
            application_name="payment-api",
            environment="dev",
        ),
        encoding="utf-8",
    )

    return target


def test_invalid_manifest_rejected_with_noop_callback(repository):
    manifest = create_manifest(repository)
    documents = list(yaml.safe_load_all(manifest.read_text()))

    documents[0]["metadata"]["labels"][
        "pod-security.kubernetes.io/enforce"
    ] = "privileged"

    manifest.write_text(
        yaml.safe_dump_all(documents),
        encoding="utf-8",
    )

    before = git(repository, "rev-parse", "HEAD")

    with pytest.raises(
        GitOpsPublishError,
        match="security validation failed",
    ):
        publish_gitops_file(
            repository_root=repository,
            values_path=manifest,
            commit_message="unsafe bootstrap",
            validate_content=lambda path: None,
        )

    assert git(repository, "rev-parse", "HEAD") == before
    assert git(repository, "diff", "--cached", "--name-only") == ""


def test_invalid_manifest_rejected_without_callback(repository):
    manifest = create_manifest(repository)
    manifest.write_text("kind: Secret\n", encoding="utf-8")

    before = git(repository, "rev-parse", "HEAD")

    with pytest.raises(
        GitOpsPublishError,
        match="security validation failed",
    ):
        publish_gitops_file(
            repository_root=repository,
            values_path=manifest,
            commit_message="unsafe bootstrap",
        )

    assert git(repository, "rev-parse", "HEAD") == before


def test_valid_manifest_commits_without_callback(repository):
    manifest = create_manifest(repository)

    commit_sha = publish_gitops_file(
        repository_root=repository,
        values_path=manifest,
        commit_message="valid bootstrap",
    )

    assert commit_sha == git(repository, "rev-parse", "HEAD")
