import subprocess
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from sqlalchemy import create_engine, delete
from sqlalchemy.orm import Session

from afterpush_api.models import Application, Deployment, Project
from afterpush_api.services.deployment_revision import (
    create_versioned_deployment,
)
from afterpush_api.services.deployment_gitops import DeploymentGitOpsSpec
from afterpush_api.services.deployment_publication import (
    publish_deployment_gitops,
)
from afterpush_api.services.deployment_recovery import (
    recover_published_deployment,
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


def test_recovery_completes_pushed_deployment(tmp_path):
    assert TEST_DATABASE_URL.rsplit("/", 1)[-1] == "afterpush_test"

    remote = tmp_path / "gitops.git"
    git("init", "--bare", "--initial-branch=main", str(remote))

    seed = tmp_path / "seed"
    git("clone", str(remote), str(seed))
    git("config", "user.name", "AfterPush Test", cwd=seed)
    git("config", "user.email", "test@afterpush.local", cwd=seed)

    (seed / "README.md").write_text("Recovery integration test\n")
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
                name=f"recovery-e2e-{uuid4().hex[:8]}",
                repository_url="https://github.com/example/source-code",
            )
            db.add(project)
            db.flush()

            application = Application(
                project_id=project.id,
                name="recovery-api",
                image="example/recovery-api",
                port=3000,
                replicas=2,
            )
            db.add(application)
            db.flush()

            deployment = create_versioned_deployment(
                db,
                application_id=application.id,
                environment="dev",
                image_tag="v12",
            )
            assert deployment is not None
            deployment.revision = 12
            deployment.status = "publishing"
            deployment.publication_claim_id = uuid4()
            deployment.publication_claimed_at = (
                datetime.now(timezone.utc) - timedelta(minutes=30)
            )
            db.add(deployment)
            db.flush()

            project_id = project.id
            application_id = application.id
            deployment_id = deployment.id

            db.commit()

        spec = DeploymentGitOpsSpec(
            application_name="recovery-api",
            environment="dev",
            image_repository="example/recovery-api",
            image_tag="v12",
            port=3000,
            replicas=2,
            project_id=project_id,
            revision=12,
        )

        published_sha = publish_deployment_gitops(
            repository_url=str(remote),
            spec=spec,
        )

        assert published_sha is not None

        with Session(engine) as db:
            application = db.get(Application, application_id)
            assert application is not None
            application.image = "example/recovery-api-changed"
            application.port = 8080
            application.replicas = 3
            db.commit()

        with Session(engine) as db:
            result = recover_published_deployment(
                db=db,
                deployment_id=deployment_id,
                gitops_repository_url=str(remote),
                timeout_minutes=15,
            )

            assert result == "recovered"

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
