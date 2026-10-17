from unittest.mock import patch
from uuid import uuid4

from sqlalchemy import create_engine, delete
from sqlalchemy.orm import Session

from afterpush_api.models import Application, Deployment, Project
from afterpush_api.services.deployment_prerequisites_dry_run import (
    inspect_pending_prerequisites,
)
from conftest import TEST_DATABASE_URL


def test_dry_run_uses_database_without_modifying_deployment():
    assert TEST_DATABASE_URL.rsplit("/", 1)[-1] == "afterpush_test"

    engine = create_engine(TEST_DATABASE_URL, pool_pre_ping=True)

    project_id = None
    application_id = None
    deployment_id = None

    try:
        with Session(engine) as db:
            project = Project(
                name=f"dry-run-e2e-{uuid4().hex[:8]}",
                repository_url="https://example.com/source.git",
            )
            db.add(project)
            db.flush()
            project_id = project.id

            application = Application(
                project_id=project_id,
                name="dry-run-api",
                image="example/dry-run-api",
                port=3000,
                replicas=2,
            )
            db.add(application)
            db.flush()
            application_id = application.id

            deployment = Deployment(
                application_id=application_id,
                environment="dev",
                image_tag="v1",
                status="pending",
                revision=1,
            )
            db.add(deployment)
            db.flush()
            deployment_id = deployment.id
            db.commit()

        with (
            patch(
                "afterpush_api.services.deployment_prerequisites_dry_run."
                "verify_namespace_bootstrap",
                return_value="test-namespace",
            ) as namespace_check,
            patch(
                "afterpush_api.services.deployment_prerequisites_dry_run."
                "verify_gitops_rbac",
                return_value=None,
            ) as rbac_check,
        ):
            with Session(engine) as db:
                results = inspect_pending_prerequisites(
                    db=db,
                    core_api=object(),
                    rbac_api=object(),
                    limit=1000,
                )

        assert results["ready"] >= 1
        assert results["errors"] == 0

        matching_namespace_calls = [
            call
            for call in namespace_check.call_args_list
            if call.kwargs["project_id"] == project_id
            and call.kwargs["application_name"] == "dry-run-api"
        ]

        matching_rbac_calls = [
            call
            for call in rbac_check.call_args_list
            if call.kwargs["project_id"] == project_id
            and call.kwargs["application_name"] == "dry-run-api"
        ]

        assert len(matching_namespace_calls) == 1
        assert len(matching_rbac_calls) == 1

        with Session(engine) as db:
            deployment = db.get(Deployment, deployment_id)

            assert deployment.status == "pending"
            assert deployment.publication_claim_id is None
            assert deployment.publication_claimed_at is None
            assert deployment.published_commit_sha is None

    finally:
        try:
            if project_id is not None:
                with Session(engine) as db:
                    if application_id is not None:
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
