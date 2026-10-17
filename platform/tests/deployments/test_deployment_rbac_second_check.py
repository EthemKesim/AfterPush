from unittest.mock import patch
from uuid import uuid4

from sqlalchemy import create_engine, delete
from sqlalchemy.orm import Session

from afterpush_api.models import Application, Deployment, Project
from afterpush_api.services.deployment_publication_worker import (
    publish_claimed_deployment,
)
from afterpush_api.services.gitops_rbac_readiness import (
    GitOpsRBACNotReady,
)
from conftest import TEST_DATABASE_URL


def test_second_rbac_check_failure_preserves_pending():
    assert TEST_DATABASE_URL.rsplit("/", 1)[-1] == "afterpush_test"

    engine = create_engine(TEST_DATABASE_URL, pool_pre_ping=True)

    project_id = None
    application_id = None
    deployment_id = None

    try:
        with Session(engine) as db:
            project = Project(
                name=f"second-rbac-{uuid4().hex[:8]}",
                repository_url="https://github.com/example/source",
            )
            db.add(project)
            db.flush()

            application = Application(
                project_id=project.id,
                name="second-rbac-api",
                image="example/second-rbac-api",
                port=3000,
                replicas=1,
            )
            db.add(application)
            db.flush()

            deployment = Deployment(
                application_id=application.id,
                environment="dev",
                image_tag="v1",
                status="pending",
                revision=1,
            )
            db.add(deployment)
            db.flush()

            project_id = project.id
            application_id = application.id
            deployment_id = deployment.id

            db.commit()

        rbac_calls = 0

        def rbac_gate(
            *,
            rbac_api,
            project_id,
            application_name,
            environment,
        ):
            nonlocal rbac_calls
            rbac_calls += 1

            if rbac_calls == 2:
                raise GitOpsRBACNotReady(
                    "RBAC permissions changed between checks."
                )

            return None

        with Session(engine) as db:
            with (
                patch(
                    "afterpush_api.services."
                    "deployment_publication_worker."
                    "check_deployment_namespace",
                    return_value="verified-namespace",
                ) as namespace_gate,
                patch(
                    "afterpush_api.services."
                    "deployment_publication_worker."
                    "verify_gitops_rbac",
                    side_effect=rbac_gate,
                ),
                patch(
                    "afterpush_api.services."
                    "deployment_publication_worker."
                    "publish_deployment_gitops",
                ) as publish,
            ):
                result = publish_claimed_deployment(
                    db=db,
                    deployment_id=deployment_id,
                    gitops_repository_url=(
                        "https://example.com/gitops.git"
                    ),
                    core_api=object(),
                    rbac_api=object(),
                )

                publish.assert_not_called()

                assert namespace_gate.call_count == 2

        assert result == "deferred"
        assert rbac_calls == 2

        # Verify actual persisted PostgreSQL state in a new session.
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
