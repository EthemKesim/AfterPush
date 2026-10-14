import subprocess
from datetime import datetime, timedelta, timezone
from unittest.mock import patch
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, delete
from sqlalchemy.orm import Session

from afterpush_api.models import Application, Deployment, Project
from afterpush_api.services.deployment_publication_worker import (
    publish_claimed_deployment,
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


def test_recovery_after_publication_completion_commit_failure(tmp_path):
    assert TEST_DATABASE_URL.rsplit("/", 1)[-1] == "afterpush_test"

    remote = tmp_path / "gitops.git"
    git("init", "--bare", "--initial-branch=main", str(remote))

    seed = tmp_path / "seed"
    git("clone", str(remote), str(seed))
    git("config", "user.name", "AfterPush Test", cwd=seed)
    git("config", "user.email", "test@afterpush.local", cwd=seed)

    (seed / "README.md").write_text("Commit failure recovery test\n")
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
                name=f"commit-failure-{uuid4().hex[:8]}",
                repository_url="https://github.com/example/source-code",
            )
            db.add(project)
            db.flush()

            application = Application(
                project_id=project.id,
                name="commit-failure-api",
                image="example/commit-failure-api",
                port=3000,
                replicas=2,
            )
            db.add(application)
            db.flush()

            deployment = Deployment(
                application_id=application.id,
                environment="dev",
                image_tag="v1",
                revision=1,
                status="pending",
            )
            db.add(deployment)
            db.flush()

            project_id = project.id
            application_id = application.id
            deployment_id = deployment.id

            db.commit()

        # Fail only the second commit: the publication completion.
        with Session(engine) as db:
            original_commit = db.commit
            commit_count = 0

            def fail_second_commit():
                nonlocal commit_count
                commit_count += 1

                if commit_count == 2:
                    raise RuntimeError(
                        "Simulated publication completion commit failure"
                    )

                return original_commit()

            with patch.object(
                db,
                "commit",
                side_effect=fail_second_commit,
            ):
                with pytest.raises(
                    RuntimeError,
                    match="Simulated publication completion commit failure",
                ):
                    publish_claimed_deployment(
                        db=db,
                        deployment_id=deployment_id,
                        gitops_repository_url=str(remote),
                    )

            assert commit_count == 2

        # Claim must remain persisted, but completion must be rolled back.
        with Session(engine) as db:
            deployment = db.get(Deployment, deployment_id)

            assert deployment.status == "publishing"
            assert deployment.publication_claim_id is not None
            assert deployment.published_commit_sha is None

            deployment.publication_claimed_at = (
                datetime.now(timezone.utc) - timedelta(minutes=30)
            )
            db.commit()

        # GitOps must have been pushed despite the failed DB completion.
        verify = tmp_path / "verify"
        git("clone", str(remote), str(verify))

        published_sha = git("rev-parse", "HEAD", cwd=verify)

        values_path = (
            verify
            / "gitops"
            / "apps"
            / "dev"
            / str(project_id)
            / "commit-failure-api"
            / "values.yaml"
        )

        assert values_path.is_file()

        # Recovery verifies the remote state before completing publication.
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
