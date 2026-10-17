import json
import os
import subprocess
import sys
from uuid import uuid4

import yaml
from sqlalchemy import create_engine, delete
from sqlalchemy.orm import Session

from afterpush_api.models import Application, Deployment, Project
from conftest import TEST_DATABASE_URL


def git(*args, cwd=None):
    return subprocess.run(
        ["git", *args],
        cwd=cwd,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def test_cli_defers_unready_namespace(tmp_path):
    assert TEST_DATABASE_URL.rsplit("/", 1)[-1] == "afterpush_test"

    remote = tmp_path / "gitops.git"
    git("init", "--bare", "--initial-branch=main", str(remote))

    seed = tmp_path / "seed"
    git("clone", str(remote), str(seed))
    git("config", "user.name", "AfterPush Test", cwd=seed)
    git("config", "user.email", "test@afterpush.local", cwd=seed)

    (seed / "README.md").write_text("AfterPush CLI E2E test\n")
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
                name=f"cli-e2e-{uuid4().hex[:8]}",
                repository_url="https://github.com/example/source-code",
            )
            db.add(project)
            db.flush()
            project_id = project.id

            application = Application(
                project_id=project_id,
                name="cli-api",
                image="example/cli-api",
                port=3000,
                replicas=2,
            )
            db.add(application)
            db.flush()
            application_id = application.id

            deployment = Deployment(
                application_id=application_id,
                environment="dev",
                image_tag="v1.0.0",
                status="pending",
                revision=1,
            )
            db.add(deployment)
            db.flush()
            deployment_id = deployment.id

            db.commit()

        env = os.environ.copy()
        env["DATABASE_URL"] = TEST_DATABASE_URL
        env["AFTERPUSH_GITOPS_REPOSITORY_URL"] = str(remote)

        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "afterpush_api.workers.gitops_publication",
                "--limit",
                "1",
                "--execute",
            ],
            env=env,
            capture_output=True,
            text=True,
            timeout=30,
        )

        assert result.returncode == 0, result.stderr

        summary = json.loads(result.stdout)
        assert summary == {
            "published": 0,
            "skipped": 0,
            "deferred": 1,
            "errors": 0,
        }

        with Session(engine) as db:
            deployment = db.get(Deployment, deployment_id)

            assert deployment.status == "pending"
            assert deployment.publication_claim_id is None
            assert deployment.publication_claimed_at is None
            assert deployment.publication_checked_at is not None
            assert deployment.published_commit_sha is None

        verify = tmp_path / "verify"
        git("clone", str(remote), str(verify))

        values_path = (
            verify
            / "gitops"
            / "apps"
            / "dev"
            / str(project_id)
            / "cli-api"
            / "values.yaml"
        )

        assert not values_path.exists()

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
