from concurrent.futures import ThreadPoolExecutor
from threading import Event
from uuid import uuid4

from sqlalchemy import create_engine, delete, text
from sqlalchemy.orm import Session

from afterpush_api.models import Application, Deployment, Project
from afterpush_api.services.deployment_claim import claim_deployment
from conftest import TEST_DATABASE_URL


def test_claim_waits_for_application_row_lock():
    assert TEST_DATABASE_URL.rsplit("/", 1)[-1] == "afterpush_test"

    engine = create_engine(TEST_DATABASE_URL, pool_pre_ping=True)

    project_id = None
    application_id = None
    deployment_id = None

    try:
        with Session(engine) as db:
            project = Project(
                name=f"claim-lock-{uuid4().hex[:8]}",
                repository_url="https://github.com/example/source",
            )
            db.add(project)
            db.flush()

            application = Application(
                project_id=project.id,
                name="claim-lock-api",
                image="example/claim-lock-api",
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

        worker_started = Event()
        worker_finished = Event()

        def worker():
            with Session(engine) as db:
                db.execute(text("SET LOCAL lock_timeout = '5s'"))
                worker_started.set()

                claim_id = claim_deployment(
                    db=db,
                    deployment_id=deployment_id,
                )

                db.commit()
                worker_finished.set()
                return claim_id

        with Session(engine) as first_db:
            first_db.execute(text("SET LOCAL lock_timeout = '5s'"))

            first_db.query(Application).filter(
                Application.id == application_id
            ).with_for_update().one()

            with ThreadPoolExecutor(max_workers=1) as executor:
                future = executor.submit(worker)

                assert worker_started.wait(timeout=5)
                assert not worker_finished.wait(timeout=0.2)

                first_db.commit()

                claim_id = future.result(timeout=10)

        assert claim_id is not None
        assert worker_finished.is_set()

        with Session(engine) as db:
            deployment = db.get(Deployment, deployment_id)

            assert deployment.status == "publishing"
            assert deployment.publication_claim_id == claim_id

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
