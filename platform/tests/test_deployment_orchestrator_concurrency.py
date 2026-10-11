
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier, Event
from uuid import uuid4

import yaml
from sqlalchemy import create_engine, delete, text
from sqlalchemy.orm import Session

from afterpush_api.models import Application, Deployment, Project
from afterpush_api.services.deployment_orchestrator import apply_deployment
from conftest import TEST_DATABASE_URL


def create_test_engine():
    assert TEST_DATABASE_URL.rsplit("/", 1)[-1] == "afterpush_test"
    return create_engine(TEST_DATABASE_URL, pool_pre_ping=True)


def create_test_records(engine, two_revisions=False):
    with Session(engine) as db:
        project = Project(
            name=f"orchestrator-{uuid4().hex[:8]}",
            repository_url="https://github.com/example/test",
        )
        db.add(project)
        db.flush()

        application = Application(
            project_id=project.id,
            name="concurrent-service",
            image="nginx",
            port=3000,
            replicas=2,
        )
        db.add(application)
        db.flush()

        first = Deployment(
            application_id=application.id,
            environment="staging",
            image_tag="v1.0.0",
            status="pending",
            revision=1,
        )
        db.add(first)
        db.flush()

        deployment_ids = [first.id]

        if two_revisions:
            second = Deployment(
                application_id=application.id,
                environment="staging",
                image_tag="v2.0.0",
                status="pending",
                revision=2,
            )
            db.add(second)
            db.flush()
            deployment_ids.append(second.id)

        result = (project.id, application.id, deployment_ids)
        db.commit()
        return result


def cleanup_test_records(engine, project_id, application_id):
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


def values_path(tmp_path):
    return (
        tmp_path
        / "apps"
        / "staging"
        / "concurrent-service"
        / "values.yaml"
    )


def test_orchestrator_waits_for_application_lock(tmp_path):
    engine = create_test_engine()
    project_id = None
    application_id = None

    try:
        project_id, application_id, deployment_ids = (
            create_test_records(engine)
        )

        worker_started = Event()
        worker_finished = Event()

        def worker():
            with Session(engine) as db:
                db.execute(text("SET LOCAL lock_timeout = '5s'"))
                worker_started.set()

                result = apply_deployment(
                    db=db,
                    deployment_id=deployment_ids[0],
                    gitops_root=tmp_path,
                )

                worker_finished.set()
                return result

        with Session(engine) as first_db:
            first_db.execute(text("SET LOCAL lock_timeout = '5s'"))

            first_db.query(Application).filter(
                Application.id == application_id
            ).with_for_update().one()

            with ThreadPoolExecutor(max_workers=1) as executor:
                future = executor.submit(worker)

                assert worker_started.wait(timeout=5)
                assert worker_finished.wait(timeout=0.2) is False

                first_db.commit()
                result = future.result(timeout=10)

        assert result == "applied"
        assert worker_finished.is_set()

        with Session(engine) as db:
            deployment = db.get(Deployment, deployment_ids[0])
            assert deployment.status == "running"

        assert values_path(tmp_path).is_file()

    finally:
        try:
            if project_id is not None:
                cleanup_test_records(engine, project_id, application_id)
        finally:
            engine.dispose()


def test_concurrent_revisions_keep_latest_gitops_version(tmp_path):
    engine = create_test_engine()
    project_id = None
    application_id = None

    try:
        project_id, application_id, deployment_ids = (
            create_test_records(engine, two_revisions=True)
        )

        barrier = Barrier(2)

        def worker(deployment_id):
            barrier.wait(timeout=10)

            with Session(engine) as db:
                db.execute(text("SET LOCAL lock_timeout = '5s'"))

                return apply_deployment(
                    db=db,
                    deployment_id=deployment_id,
                    gitops_root=tmp_path,
                )

        with ThreadPoolExecutor(max_workers=2) as executor:
            futures = [
                executor.submit(worker, deployment_id)
                for deployment_id in deployment_ids
            ]

            results = [
                future.result(timeout=15)
                for future in futures
            ]

        assert sorted(results) == ["applied", "skipped"]

        with Session(engine) as db:
            first = db.get(Deployment, deployment_ids[0])
            second = db.get(Deployment, deployment_ids[1])

            assert first.status == "pending"
            assert second.status == "running"

        with values_path(tmp_path).open("r", encoding="utf-8") as file:
            values = yaml.safe_load(file)

        assert values["image"]["tag"] == "v2.0.0"
        assert values["image"]["repository"] == "nginx"

    finally:
        try:
            if project_id is not None:
                cleanup_test_records(engine, project_id, application_id)
        finally:
            engine.dispose()
