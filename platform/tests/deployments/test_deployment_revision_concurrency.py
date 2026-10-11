
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier, Event
from uuid import uuid4

from sqlalchemy import create_engine, delete, text
from sqlalchemy.orm import Session

from afterpush_api.models import Application, Deployment, Project
from afterpush_api.services.deployment_revision import (
    create_versioned_deployment,
)
from conftest import TEST_DATABASE_URL


def create_test_engine():
    assert TEST_DATABASE_URL.rsplit("/", 1)[-1] == "afterpush_test", (
        "Concurrency tests must use the afterpush_test database"
    )

    return create_engine(
        TEST_DATABASE_URL,
        pool_pre_ping=True,
    )


def create_test_application(engine):
    with Session(engine) as db:
        project = Project(
            name=f"concurrency-{uuid4().hex[:8]}",
            repository_url="https://github.com/example/concurrency",
        )

        db.add(project)
        db.flush()

        application = Application(
            project_id=project.id,
            name="concurrent-api",
            image="nginx",
            port=3000,
            replicas=1,
        )

        db.add(application)
        db.flush()

        project_id = project.id
        application_id = application.id

        db.commit()

    return project_id, application_id


def cleanup_test_application(engine, project_id, application_id):
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


def test_concurrent_deployments_get_unique_revisions():
    engine = create_test_engine()
    project_id = None
    application_id = None

    try:
        project_id, application_id = create_test_application(engine)

        barrier = Barrier(2)

        def worker(image_tag):
            barrier.wait(timeout=10)

            with Session(engine) as db:
                deployment = create_versioned_deployment(
                    db=db,
                    application_id=application_id,
                    environment="staging",
                    image_tag=image_tag,
                )

                assert deployment is not None
                revision = deployment.revision

                db.commit()
                return revision

        with ThreadPoolExecutor(max_workers=2) as executor:
            first = executor.submit(worker, "v1.0.0")
            second = executor.submit(worker, "v1.1.0")

            revisions = [
                first.result(timeout=15),
                second.result(timeout=15),
            ]

        assert sorted(revisions) == [1, 2]

        with Session(engine) as db:
            deployments = (
                db.query(Deployment)
                .filter(
                    Deployment.application_id == application_id,
                    Deployment.environment == "staging",
                )
                .all()
            )

            assert len(deployments) == 2
            assert sorted(
                deployment.revision
                for deployment in deployments
            ) == [1, 2]

    finally:
        try:
            if project_id is not None:
                cleanup_test_application(
                    engine,
                    project_id,
                    application_id,
                )
        finally:
            engine.dispose()


def test_second_deployment_waits_for_first_transaction():
    engine = create_test_engine()
    project_id = None
    application_id = None

    try:
        project_id, application_id = create_test_application(engine)

        worker_started = Event()
        worker_finished = Event()

        def second_worker():
            with Session(engine) as db:
                # Prevent an indefinite wait if locking breaks.
                db.execute(
                    text("SET LOCAL lock_timeout = '5s'")
                )

                worker_started.set()

                deployment = create_versioned_deployment(
                    db=db,
                    application_id=application_id,
                    environment="staging",
                    image_tag="v2.0.0",
                )

                assert deployment is not None

                revision = deployment.revision
                db.commit()

                worker_finished.set()
                return revision

        with Session(engine) as first_db:
            first_deployment = create_versioned_deployment(
                db=first_db,
                application_id=application_id,
                environment="staging",
                image_tag="v1.0.0",
            )

            assert first_deployment is not None
            assert first_deployment.revision == 1

            # The first transaction still holds the application lock.
            with ThreadPoolExecutor(max_workers=1) as executor:
                future = executor.submit(second_worker)

                assert worker_started.wait(timeout=5)

                # Confirm that the second worker has not completed
                # while the first transaction is still open.
                assert worker_finished.wait(timeout=0.2) is False

                # Release the first transaction's row lock.
                first_db.commit()

                second_revision = future.result(timeout=10)

        assert second_revision == 2
        assert worker_finished.is_set()

        with Session(engine) as db:
            revisions = (
                db.query(Deployment.revision)
                .filter(
                    Deployment.application_id == application_id,
                    Deployment.environment == "staging",
                )
                .all()
            )

            assert sorted(revision for (revision,) in revisions) == [
                1, 2
            ]

    finally:
        try:
            if project_id is not None:
                cleanup_test_application(
                    engine,
                    project_id,
                    application_id,
                )
        finally:
            engine.dispose()
