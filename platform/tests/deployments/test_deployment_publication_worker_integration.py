import subprocess
from uuid import uuid4

import yaml
from sqlalchemy import create_engine, delete
from sqlalchemy.orm import Session

from afterpush_api.models import Application, Deployment, Project
from afterpush_api.services.deployment_publication_worker import (
    publish_claimed_deployment,
)
from conftest import TEST_DATABASE_URL


def git(*args, cwd=None):
    return subprocess.run(
        ["git", *args],
        cwd=cwd,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def test_publication_worker_persists_gitops_commit(tmp_path):
    assert TEST_DATABASE_URL.rsplit("/", 1)[-1] == "afterpush_test"

    remote = tmp_path / "gitops.git"
    git("init", "--bare", "--initial-branch=main", str(remote))

    seed = tmp_path / "seed"
    git("clone", str(remote), str(seed))
    git("config", "user.name", "AfterPush Test", cwd=seed)
    git("config", "user.email", "test@afterpush.local", cwd=seed)

    (seed / "README.md").write_text("AfterPush GitOps test\n")
    git("add", "README.md", cwd=seed)
    git("commit", "-m", "Initial commit", cwd=seed)
    git("push", "origin", "HEAD:refs/heads/main", cwd=seed)

    engine = create_engine(TEST_DATABASE_URL, pool_pre_ping=True)

    project_id = None
    application_id = None
    deployment_id = None

    try:
        with Session(engine) as db:
            project = Project(
                name=f"worker-e2e-{uuid4().hex[:8]}",
                repository_url="https://github.com/example/source-code",
            )
            db.add(project)
            db.flush()

            application = Application(
                project_id=project.id,
                name="worker-api",
                image="example/worker-api",
                port=3000,
                replicas=2,
            )
            db.add(application)
            db.flush()

            deployment = Deployment(
                application_id=application.id,
                environment="dev",
                image_tag="v1.0.0",
                status="pending",
                revision=1,
            )
            db.add(deployment)
            db.flush()

            project_id = project.id
            application_id = application.id
            deployment_id = deployment.id

            db.commit()

        with Session(engine) as db:
            result = publish_claimed_deployment(
                db=db,
                deployment_id=deployment_id,
                gitops_repository_url=str(remote),
            )

            assert result == "published"

        with Session(engine) as db:
            deployment = db.get(Deployment, deployment_id)

            assert deployment is not None
            assert deployment.status == "published"
            assert deployment.publication_claim_id is None
            assert deployment.publication_claimed_at is None

            published_sha = deployment.published_commit_sha

            assert published_sha is not None
            assert len(published_sha) == 40

        verify = tmp_path / "verify"
        git("clone", str(remote), str(verify))

        assert git("rev-parse", "HEAD", cwd=verify) == published_sha

        values_path = (
            verify
            / "gitops"
            / "apps"
            / "dev"
            / str(project_id)
            / "worker-api"
            / "values.yaml"
        )

        values = yaml.safe_load(values_path.read_text())

        assert values["deployment"]["revision"] == 1
        assert values["image"]["repository"] == "example/worker-api"
        assert values["image"]["tag"] == "v1.0.0"

    finally:
        try:
            if project_id is not None:
                with Session(engine) as db:
                    db.execute(
                        delete(Deployment).where(
                            Deployment.application_id == application_id
                        )
                    )
                    db.execute(
                        delete(Application).where(
                            Application.id == application_id
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
