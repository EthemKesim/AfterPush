from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from uuid import uuid4

from sqlalchemy import create_engine, delete, text
from sqlalchemy.orm import Session

from afterpush_api.models import Application, Deployment, Project
from afterpush_api.services.deployment_claim import claim_deployment
from conftest import TEST_DATABASE_URL


def test_concurrent_revision_claims_only_claim_latest():
    assert TEST_DATABASE_URL.rsplit("/", 1)[-1] == "afterpush_test"

    engine = create_engine(TEST_DATABASE_URL, pool_pre_ping=True)
    project_id = None
    application_id = None

    try:
        with Session(engine) as db:
            project = Project(
                name=f"revision-claim-{uuid4().hex[:8]}",
                repository_url="https://github.com/example/source",
            )
            db.add(project)
            db.flush()

            application = Application(
                project_id=project.id,
                name="revision-claim-api",
                image="example/revision-claim-api",
                port=3000,
                replicas=2,
            )
            db.add(application)
            db.flush()

            first = Deployment(
                application_id=application.id,
                environment="dev",
                image_tag="v1",
                revision=1,
                status="pending",
            )
            second = Deployment(
                application_id=application.id,
                environment="dev",
                image_tag="v2",
                revision=2,
                status="pending",
            )

            db.add_all([first, second])
            db.flush()

            project_id = project.id
            application_id = application.id
            first_id = first.id
            second_id = second.id
            db.commit()

        barrier = Barrier(2)

        def worker(deployment_id):
            with Session(engine) as db:
                db.execute(text("SET LOCAL lock_timeout = '5s'"))
                barrier.wait(timeout=10)

                claim_id = claim_deployment(
                    db=db,
                    deployment_id=deployment_id,
                )
                db.commit()
                return claim_id

        with ThreadPoolExecutor(max_workers=2) as executor:
            futures = [
                executor.submit(worker, first_id),
                executor.submit(worker, second_id),
            ]
            results = [future.result(timeout=15) for future in futures]

        assert results[0] is None
        assert results[1] is not None

        with Session(engine) as db:
            first = db.get(Deployment, first_id)
            second = db.get(Deployment, second_id)

            assert first.status == "pending"
            assert first.publication_claim_id is None

            assert second.status == "publishing"
            assert second.publication_claim_id == results[1]
            assert second.publication_claimed_at is not None

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
                        delete(Project).where(Project.id == project_id)
                    )
                    db.commit()
        finally:
            engine.dispose()
