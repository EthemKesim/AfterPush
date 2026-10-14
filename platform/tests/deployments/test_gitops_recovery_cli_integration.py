import json
import os
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from sqlalchemy import create_engine, delete
from sqlalchemy.orm import Session

from afterpush_api.models import Application, Deployment, Project
from afterpush_api.services.deployment_gitops import DeploymentGitOpsSpec
from afterpush_api.services.deployment_publication import (
    publish_deployment_gitops,
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


def test_recovery_cli_completes_published_deployment(tmp_path):
    assert TEST_DATABASE_URL.rsplit("/", 1)[-1] == "afterpush_test"

    remote = tmp_path / "gitops.git"
    git("init", "--bare", "--initial-branch=main", str(remote))

    seed = tmp_path / "seed"
    git("clone", str(remote), str(seed))
    git("config", "user.name", "AfterPush Test", cwd=seed)
    git("config", "user.email", "test@afterpush.local", cwd=seed)

    (seed / "README.md").write_text("Recovery CLI integration test\n")
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
                name=f"recovery-cli-{uuid4().hex[:8]}",
                repository_url="https://github.com/example/source-code",
            )
            db.add(project)
            db.flush()
            project_id = project.id

            application = Application(
                project_id=project_id,
                name="recovery-cli-api",
                image="example/recovery-cli-api",
                port=3000,
                replicas=2,
            )
            db.add(application)
            db.flush()
            application_id = application.id

            deployment = Deployment(
                application_id=application_id,
                environment="dev",
                image_tag="v15",
                revision=15,
                status="publishing",
                publication_claim_id=uuid4(),
                publication_claimed_at=(
                    datetime.now(timezone.utc) - timedelta(minutes=30)
                ),
            )
            db.add(deployment)
            db.flush()
            deployment_id = deployment.id
            db.commit()

        spec = DeploymentGitOpsSpec(
            application_name="recovery-cli-api",
            environment="dev",
            image_repository="example/recovery-cli-api",
            image_tag="v15",
            port=3000,
            replicas=2,
            project_id=project_id,
            revision=15,
        )

        published_sha = publish_deployment_gitops(
            repository_url=str(remote),
            spec=spec,
        )

        env = os.environ.copy()
        env["DATABASE_URL"] = TEST_DATABASE_URL
        env["AFTERPUSH_GITOPS_REPOSITORY_URL"] = str(remote)

        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "afterpush_api.workers.gitops_recovery",
                "--timeout-minutes",
                "15",
                "--limit",
                "1",
            ],
            env=env,
            capture_output=True,
            text=True,
            timeout=30,
        )

        assert result.returncode == 0, result.stderr

        summary = json.loads(result.stdout)
        assert summary == {
            "recovered": 1,
            "not_published": 0,
            "not_eligible": 0,
            "not_found": 0,
            "claim_changed": 0,
            "errors": 0,
        }

        with Session(engine) as db:
            deployment = db.get(Deployment, deployment_id)

            assert deployment.status == "published"
            assert deployment.published_commit_sha == published_sha
            assert deployment.publication_claim_id is None
            assert deployment.publication_claimed_at is None

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
