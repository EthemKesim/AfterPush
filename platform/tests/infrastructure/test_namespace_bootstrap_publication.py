import subprocess
from uuid import UUID

import pytest
import yaml

from afterpush_api.services.namespace_bootstrap_publication import (
    NamespaceBootstrapPublicationSpec,
    publish_namespace_bootstrap,
)


PROJECT_ID = UUID("12471cf9-11d4-4089-ad0d-2c4b777fc227")


def git(*args, cwd=None):
    result = subprocess.run(
        ["git", *args],
        cwd=cwd,
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


@pytest.fixture
def gitops_remote(tmp_path):
    remote = tmp_path / "gitops.git"

    git(
        "init",
        "--bare",
        "--initial-branch=main",
        str(remote),
    )

    seed = tmp_path / "seed"
    git("clone", str(remote), str(seed))
    git("config", "user.name", "AfterPush Test", cwd=seed)
    git(
        "config",
        "user.email",
        "test@afterpush.local",
        cwd=seed,
    )

    (seed / "README.md").write_text(
        "Local namespace bootstrap integration test\n",
        encoding="utf-8",
    )

    git("add", "README.md", cwd=seed)
    git("commit", "-m", "Initial commit", cwd=seed)
    git("push", "origin", "HEAD:refs/heads/main", cwd=seed)

    return remote


def make_spec(environment="dev"):
    return NamespaceBootstrapPublicationSpec(
        project_id=PROJECT_ID,
        application_name="payment-api",
        environment=environment,
    )


def checkout_remote(remote, destination):
    git("clone", str(remote), str(destination))
    return destination


def bootstrap_path(checkout, environment="dev"):
    return (
        checkout
        / "gitops"
        / "platform"
        / "namespaces"
        / environment
        / str(PROJECT_ID)
        / "namespace.yaml"
    )


def test_publishes_validated_namespace_manifest(
    gitops_remote,
    tmp_path,
):
    commit_sha = publish_namespace_bootstrap(
        repository_url=str(gitops_remote),
        spec=make_spec(),
    )

    checkout = checkout_remote(
        gitops_remote,
        tmp_path / "verify",
    )

    assert git("rev-parse", "HEAD", cwd=checkout) == commit_sha

    manifest = bootstrap_path(checkout)
    assert manifest.is_file()

    documents = list(
        yaml.safe_load_all(manifest.read_text(encoding="utf-8"))
    )

    assert len(documents) == 3

    assert [doc["kind"] for doc in documents] == [
        "Namespace",
        "ResourceQuota",
        "LimitRange",
    ]

    namespace = documents[0]

    assert namespace["metadata"]["name"] == (
        f"ap-dev-{PROJECT_ID}"
    )

    labels = namespace["metadata"]["labels"]

    assert labels["pod-security.kubernetes.io/enforce"] == (
        "restricted"
    )


def test_repeated_publication_is_idempotent(
    gitops_remote,
    tmp_path,
):
    first_sha = publish_namespace_bootstrap(
        repository_url=str(gitops_remote),
        spec=make_spec(),
    )

    second_sha = publish_namespace_bootstrap(
        repository_url=str(gitops_remote),
        spec=make_spec(),
    )

    assert second_sha == first_sha

    checkout = checkout_remote(
        gitops_remote,
        tmp_path / "verify-idempotency",
    )

    assert git("rev-parse", "HEAD", cwd=checkout) == first_sha

    assert git("rev-list", "--count", "HEAD", cwd=checkout) == (
        "2"
    )


def test_rejects_conflicting_existing_policy(
    gitops_remote,
    tmp_path,
):
    checkout = checkout_remote(
        gitops_remote,
        tmp_path / "conflicting-checkout",
    )

    manifest = bootstrap_path(checkout)
    manifest.parent.mkdir(parents=True, exist_ok=True)

    manifest.write_text(
        "apiVersion: v1\n"
        "kind: Namespace\n"
        "metadata:\n"
        "  name: unsafe-namespace\n",
        encoding="utf-8",
    )

    git("add", ".", cwd=checkout)
    git(
        "commit",
        "-m",
        "Introduce conflicting policy",
        cwd=checkout,
    )
    git("push", "origin", "HEAD:refs/heads/main", cwd=checkout)

    before = git("rev-parse", "HEAD", cwd=checkout)

    with pytest.raises(
        ValueError,
        match="differs from expected policy",
    ):
        publish_namespace_bootstrap(
            repository_url=str(gitops_remote),
            spec=make_spec(),
        )

    verify = checkout_remote(
        gitops_remote,
        tmp_path / "verify-conflict",
    )

    assert git("rev-parse", "HEAD", cwd=verify) == before


def test_rejects_invalid_environment(gitops_remote):
    with pytest.raises(ValueError, match="Invalid"):
        publish_namespace_bootstrap(
            repository_url=str(gitops_remote),
            spec=make_spec(environment="production"),
        )


def test_rejects_empty_repository_url():
    with pytest.raises(ValueError, match="cannot be empty"):
        publish_namespace_bootstrap(
            repository_url="",
            spec=make_spec(),
        )


def test_rejects_invalid_attempt_count(gitops_remote):
    with pytest.raises(
        ValueError,
        match="max_attempts",
    ):
        publish_namespace_bootstrap(
            repository_url=str(gitops_remote),
            spec=make_spec(),
            max_attempts=0,
        )
