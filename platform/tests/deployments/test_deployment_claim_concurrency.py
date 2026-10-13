from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from uuid import uuid4

from sqlalchemy import create_engine, delete, text
from sqlalchemy.orm import Session

from afterpush_api.models import Application, Deployment, Project
from afterpush_api.services.deployment_claim import claim_deployment
from conftest import TEST_DATABASE_URL


def test_only_one_worker_can_claim_same_deployment():
    assert TEST_DATABASE_URL.rsplit("/", 1)[-1] == "afterpush_test"

    engine = create_engine(
        TEST_DATABASE_URL,
        pool_pre_ping=True,
    )

    project_id = None
    application_id = None
    deployment_id = None

    try:
        with Session(engine) as db:
            project = Project(
                name=f"claim-concurrency-{uuid4().hex[:8]}",
                repository_url="https://github.com/example/claim-test",
            )
            db.add(project)
            db.flush()

            application = Application(
                project_id=project.id,
                name="claim-api",
                image="nginx",
                port=3000,
                replicas=1,
            )
            db.add(application)
            db.flush()

            deployment = Deployment(
                application_id=application.id,
                environment="staging",
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

        barrier = Barrier(2)

        def worker():
            with Session(engine) as db:
                db.execute(
                    text("SET LOCAL lock_timeout = '5s'")
                )

                barrier.wait(timeout=10)

                claim_id = claim_deployment(
                    db=db,
                    deployment_id=deployment_id,
                )

                db.commit()
                return claim_id

        with ThreadPoolExecutor(max_workers=2) as executor:
            first = executor.submit(worker)
            second = executor.submit(worker)

            results = [
                first.result(timeout=15),
                second.result(timeout=15),
            ]

        successful_claims = [
            claim_id
            for claim_id in results
            if claim_id is not None
        ]

        assert len(successful_claims) == 1

        with Session(engine) as db:
            deployment = db.get(Deployment, deployment_id)

            assert deployment is not None
            assert deployment.status == "publishing"
            assert deployment.publication_claim_id == successful_claims[0]
            assert deployment.publication_claimed_at is not None

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
