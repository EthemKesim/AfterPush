import subprocess
from uuid import uuid4
from unittest.mock import patch

import yaml
from sqlalchemy import create_engine, delete
from sqlalchemy.orm import Session

from afterpush_api.models import Application, Deployment, Project
from afterpush_api.services.deployment_publication_worker import (
    process_pending_publications,
)
from conftest import TEST_DATABASE_URL


def patch_namespace_gate():
    return patch(
        "afterpush_api.services.deployment_publication_worker."
        "check_deployment_namespace",
        return_value="verified-test-namespace",
    )


def git(*args, cwd=None):
    return subprocess.run(
        ["git", *args],
        cwd=cwd,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def test_batch_publishes_multiple_deployments(tmp_path):
    assert TEST_DATABASE_URL.rsplit("/", 1)[-1] == "afterpush_test"

    remote = tmp_path / "gitops.git"
    git("init", "--bare", "--initial-branch=main", str(remote))

    seed = tmp_path / "seed"
    git("clone", str(remote), str(seed))
    git("config", "user.name", "AfterPush Test", cwd=seed)
    git("config", "user.email", "test@afterpush.local", cwd=seed)

    (seed / "README.md").write_text("AfterPush batch test\n")
    git("add", "README.md", cwd=seed)
    git("commit", "-m", "Initial commit", cwd=seed)
    git("push", "origin", "HEAD:refs/heads/main", cwd=seed)

    engine = create_engine(TEST_DATABASE_URL, pool_pre_ping=True)

    project_id = None
    application_ids = []
    deployment_ids = []

    try:
        with Session(engine) as db:
            project = Project(
                name=f"batch-e2e-{uuid4().hex[:8]}",
                repository_url="https://github.com/example/source-code",
            )
            db.add(project)
            db.flush()
            project_id = project.id

            for index in range(2):
                application = Application(
                    project_id=project_id,
                    name=f"batch-api-{index}",
                    image=f"example/batch-api-{index}",
                    port=3000,
                    replicas=2,
                )
                db.add(application)
                db.flush()
                application_ids.append(application.id)

                deployment = Deployment(
                    application_id=application.id,
                    environment="dev",
                    image_tag=f"v1.0.{index}",
                    status="pending",
                    revision=1,
                )
                db.add(deployment)
                db.flush()
                deployment_ids.append(deployment.id)

            db.commit()

        with Session(engine) as db:
            with (
                patch_namespace_gate(),
                patch(
                    "afterpush_api.services.deployment_publication_worker."
                    "verify_gitops_rbac",
                    return_value=None,
                ),
            ):
                result = process_pending_publications(
                    db=db,
                    gitops_repository_url=str(remote),
                    limit=20,
                    core_api=object(),
                )

            assert result["published"] >= 2
            assert result["errors"] == 0

        with Session(engine) as db:
            for deployment_id in deployment_ids:
                deployment = db.get(Deployment, deployment_id)

                assert deployment.status == "published"
                assert deployment.published_commit_sha is not None
                assert len(deployment.published_commit_sha) == 40
                assert deployment.publication_claim_id is None

        verify = tmp_path / "verify"
        git("clone", str(remote), str(verify))

        for index in range(2):
            values_path = (
                verify
                / "gitops"
                / "apps"
                / "dev"
                / str(project_id)
                / f"batch-api-{index}"
                / "values.yaml"
            )

            assert values_path.is_file()

            values = yaml.safe_load(values_path.read_text())

            assert values["deployment"]["revision"] == 1
            assert values["image"]["repository"] == f"example/batch-api-{index}"
            assert values["image"]["tag"] == f"v1.0.{index}"

    finally:
        try:
            if project_id is not None:
                with Session(engine) as db:
                    db.execute(
                        delete(Deployment).where(
                            Deployment.application_id.in_(application_ids)
                        )
                    )
                    db.execute(
                        delete(Application).where(
                            Application.id.in_(application_ids)
                        )
                    )
                    db.execute(
                        delete(Project).where(
                            Project.id == project_id
                        )
                    )
                    db.commit()
        finally:
            engine.dispose()
