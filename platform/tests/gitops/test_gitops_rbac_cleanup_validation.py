import subprocess
from pathlib import Path
from uuid import uuid4

import yaml

from afterpush_api.services.gitops_rbac_cleanup import (
    RBACCleanupCandidate,
)
from afterpush_api.services.gitops_rbac_cleanup_validation import (
    verify_cleanup_candidate,
)
from afterpush_api.services.gitops_rbac_preparation import (
    prepare_gitops_rbac,
)
from afterpush_api.services.gitops_rbac_selection import (
    RBACPublicationTarget,
)


def git(repository, *args):
    subprocess.run(
        ["git", "-C", str(repository), *args],
        check=True,
        capture_output=True,
        text=True,
    )


def setup_rbac(repository):
    git(repository, "init", "-q")

    target = RBACPublicationTarget(
        project_id=uuid4(),
        application_name="backend",
        environment="dev",
    )

    paths = prepare_gitops_rbac(
        repository_root=repository,
        project_id=target.project_id,
        application_name=target.application_name,
        environment=target.environment,
    )

    directory = Path(paths[0]).parent

    candidate = RBACCleanupCandidate(
        target=target,
        relative_directory=directory.relative_to(repository),
    )

    return candidate, paths


def test_valid_generated_rbac_is_accepted(tmp_path):
    candidate, paths = setup_rbac(tmp_path)

    git(tmp_path, "add", "--", str(candidate.relative_directory))
    git(tmp_path, "-c", "user.name=AfterPush Test",
        "-c", "user.email=test@afterpush.local",
        "commit", "-qm", "Add RBAC manifests")

    assert verify_cleanup_candidate(
        repository_root=tmp_path,
        candidate=candidate,
    )


def test_deployment_delete_permission_is_rejected(tmp_path):
    candidate, paths = setup_rbac(tmp_path)

    deployment_path = next(
        path for path in paths
        if Path(path).name == "deployment-rbac.yaml"
    )

    documents = list(yaml.safe_load_all(
        Path(deployment_path).read_text()
    ))

    role = next(
        document for document in documents
        if document["kind"] == "Role"
    )

    role["rules"][0]["verbs"].append("delete")

    Path(deployment_path).write_text(
        yaml.safe_dump_all(documents, sort_keys=False)
    )

    git(tmp_path, "add", "--", str(candidate.relative_directory))

    assert not verify_cleanup_candidate(
        repository_root=tmp_path,
        candidate=candidate,
    )


def test_argocd_broad_access_is_rejected(tmp_path):
    candidate, paths = setup_rbac(tmp_path)

    argocd_path = next(
        path for path in paths
        if Path(path).name == "argocd-rbac.yaml"
    )

    documents = list(yaml.safe_load_all(
        Path(argocd_path).read_text()
    ))

    role = next(
        document for document in documents
        if document["kind"] == "Role"
    )

    role["rules"][0]["resourceNames"] = ["*"]

    Path(argocd_path).write_text(
        yaml.safe_dump_all(documents, sort_keys=False)
    )

    git(tmp_path, "add", "--", str(candidate.relative_directory))

    assert not verify_cleanup_candidate(
        repository_root=tmp_path,
        candidate=candidate,
    )


def test_untracked_manifest_is_rejected(tmp_path):
    candidate, paths = setup_rbac(tmp_path)

    git(
        tmp_path,
        "add",
        "--",
        str(candidate.relative_directory / "argocd-rbac.yaml"),
    )

    assert not verify_cleanup_candidate(
        repository_root=tmp_path,
        candidate=candidate,
    )
