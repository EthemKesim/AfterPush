import subprocess
from pathlib import Path
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
from afterpush_api.services.namespace_bootstrap_validator import (
    validate_namespace_bootstrap,
)


PROJECT_ID = UUID("12471cf9-11d4-4089-ad0d-2c4b777fc227")
APPLICATION_NAME = "payment-api"
ENVIRONMENT = "dev"


def git(root: Path, *arguments: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(root), *arguments],
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout.strip()


@pytest.fixture
def repository(tmp_path):
    root = tmp_path / "repository"
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
        / "gitops"
        / "platform"
        / "namespaces"
        / ENVIRONMENT
        / str(PROJECT_ID)
        / "namespace.yaml"
    )

    target.parent.mkdir(parents=True, exist_ok=True)

    rendered = render_namespace_bootstrap(
        project_id=PROJECT_ID,
        application_name=APPLICATION_NAME,
        environment=ENVIRONMENT,
    )

    target.write_text(rendered, encoding="utf-8")
    return target


def validate_content(path):
    validate_namespace_bootstrap(
        rendered_yaml=path.read_text(encoding="utf-8"),
        project_id=PROJECT_ID,
        application_name=APPLICATION_NAME,
        environment=ENVIRONMENT,
    )


def mutate_manifest(path, mutation):
    documents = list(yaml.safe_load_all(path.read_text()))
    mutation(documents)

    path.write_text(
        yaml.safe_dump_all(documents, sort_keys=False),
        encoding="utf-8",
    )


def remove_pod_security(documents):
    documents[0]["metadata"]["labels"].pop(
        "pod-security.kubernetes.io/enforce"
    )


def weaken_pod_security(documents):
    documents[0]["metadata"]["labels"][
        "pod-security.kubernetes.io/enforce"
    ] = "privileged"


def increase_resource_quota(documents):
    documents[1]["spec"]["hard"]["requests.cpu"] = "100"


def remove_limit_range(documents):
    documents.pop(2)


def add_secret(documents):
    documents.append(
        {
            "apiVersion": "v1",
            "kind": "Secret",
            "metadata": {"name": "unexpected-secret"},
            "data": {},
        }
    )


@pytest.mark.parametrize(
    "mutation",
    [
        remove_pod_security,
        weaken_pod_security,
        increase_resource_quota,
        remove_limit_range,
        add_secret,
    ],
)
def test_unsafe_namespace_manifest_never_commits(
    repository,
    mutation,
):
    manifest = create_manifest(repository)
    mutate_manifest(manifest, mutation)

    original_head = git(repository, "rev-parse", "HEAD")

    with pytest.raises(GitOpsPublishError):
        publish_gitops_file(
            repository_root=repository,
            values_path=manifest,
            commit_message="unsafe namespace bootstrap",
            validate_content=validate_content,
        )

    assert git(repository, "rev-parse", "HEAD") == original_head

    assert (
        git(repository, "diff", "--cached", "--name-only")
        == ""
    )


def test_valid_namespace_manifest_commits(repository):
    manifest = create_manifest(repository)

    commit_sha = publish_gitops_file(
        repository_root=repository,
        values_path=manifest,
        commit_message="valid namespace bootstrap",
        validate_content=validate_content,
    )

    assert commit_sha == git(repository, "rev-parse", "HEAD")

    assert git(
        repository,
        "show",
        "--format=",
        "--name-only",
        "HEAD",
    ) == (
        f"gitops/platform/namespaces/dev/{PROJECT_ID}/namespace.yaml"
    )
