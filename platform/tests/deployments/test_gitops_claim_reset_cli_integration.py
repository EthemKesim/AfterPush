import json
import os
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from sqlalchemy import create_engine, delete
from sqlalchemy.orm import Session

from afterpush_api.models import Application, Deployment, Project
from afterpush_api.services.deployment_revision import (
    create_versioned_deployment,
)
from conftest import TEST_DATABASE_URL


def test_claim_reset_cli_resets_confirmed_stale_claim():
    engine = create_engine(TEST_DATABASE_URL, pool_pre_ping=True)
    project_id = None
    application_id = None

    try:
        with Session(engine) as db:
            project = Project(
                name=f"claim-reset-cli-{uuid4().hex[:8]}",
                repository_url="https://example.com/claim-reset-cli.git",
            )
            db.add(project)
            db.flush()
            project_id = project.id

            application = Application(
                project_id=project_id,
                name="claim-reset-cli-api",
                image="example/claim-reset-cli-api",
                port=3000,
                replicas=2,
            )
            db.add(application)
            db.flush()
            application_id = application.id

            deployment = create_versioned_deployment(
                db,
                application_id=application_id,
                environment="dev",
                image_tag="v1",
            )
            assert deployment is not None
            deployment.status = "publishing"
            deployment.publication_claim_id = uuid4()
            deployment.publication_claimed_at = (
                datetime.now(timezone.utc) - timedelta(minutes=30)
            )
            deployment_id = deployment.id
            claim_id = deployment.publication_claim_id
            db.commit()

        environment = os.environ.copy()
        environment["DATABASE_URL"] = TEST_DATABASE_URL

        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "afterpush_api.workers.gitops_claim_reset",
                "--deployment-id",
                str(deployment_id),
                "--claim-id",
                str(claim_id),
                "--timeout-minutes",
                "15",
                "--confirm-worker-stopped",
            ],
            env=environment,
            capture_output=True,
            text=True,
            timeout=30,
        )

        assert result.returncode == 0, result.stderr
        assert json.loads(result.stdout) == {
            "deployment_id": str(deployment_id),
            "result": "reset",
        }

        with Session(engine) as db:
            deployment = db.get(Deployment, deployment_id)
            assert deployment is not None
            assert deployment.status == "pending"
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
                        delete(Project).where(Project.id == project_id))
                    db.commit()
        finally:
            engine.dispose()
