
import fcntl
import multiprocessing
import threading
from pathlib import Path
from uuid import UUID, uuid4

import yaml
from sqlalchemy import create_engine, delete
from sqlalchemy.orm import Session

from afterpush_api.models import Application, Deployment, Project
from afterpush_api.services.deployment_reconciliation import (
    check_deployment_drift,
)
from afterpush_api.services.gitops import get_values_path
from afterpush_api.services.locking import gitops_application_lock
from conftest import TEST_DATABASE_URL


def hold_gitops_lock(
    root: str,
    project_id: UUID,
    locked,
    release,
):
    with gitops_application_lock(
        gitops_root=Path(root),
        application_name="reconciliation-api",
        environment="staging",
        project_id=project_id,
    ):
        locked.set()

        if not release.wait(timeout=10):
            raise TimeoutError("Lock release was not signaled")


def prepare_reconciliation_data(engine, tmp_path):
    with Session(engine) as db:
        project = Project(
            name=f"lock-test-{uuid4().hex[:8]}",
            repository_url="https://github.com/example/project",
        )
        db.add(project)
        db.flush()

        application = Application(
            project_id=project.id,
            name="reconciliation-api",
            image="nginx",
            port=3000,
            replicas=2,
        )
        db.add(application)
        db.flush()

        deployment = Deployment(
            application_id=application.id,
            environment="staging",
            image_tag="v2.0.0",
            status="running",
            revision=1,
        )
        db.add(deployment)
        db.flush()

        project_id = project.id
        application_id = application.id
        db.commit()

    values_path = get_values_path(
        gitops_root=tmp_path,
        application_name="reconciliation-api",
        environment="staging",
        project_id=project_id,
    )
    values_path.parent.mkdir(parents=True, exist_ok=True)

    with values_path.open("w", encoding="utf-8") as file:
        yaml.safe_dump(
            {"image": {"repository": "nginx", "tag": "v2.0.0"}},
            file,
        )

    return project_id, application_id


def cleanup_reconciliation_data(
    engine,
    project_id,
    application_id,
):
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


def test_reconciliation_waits_for_gitops_lock(tmp_path):
    engine = create_engine(TEST_DATABASE_URL, pool_pre_ping=True)

    project_id = None
    application_id = None

    try:
        project_id, application_id = prepare_reconciliation_data(
            engine, tmp_path
        )

        context = multiprocessing.get_context("spawn")
        locked = context.Event()
        release = context.Event()

        started = threading.Event()
        finished = threading.Event()
        results = []
        errors = []

        def reconciliation_worker():
            try:
                with Session(engine) as db:
                    started.set()

                    result = check_deployment_drift(
                        db=db,
                        application_id=application_id,
                        environment="staging",
                        gitops_root=tmp_path,
                    )

                    results.append(result)

            except Exception as error:
                errors.append(error)

            finally:
                finished.set()

        process = context.Process(
            target=hold_gitops_lock,
            args=(str(tmp_path), project_id, locked, release),
        )

        worker = threading.Thread(
            target=reconciliation_worker,
            daemon=True,
        )

        process.start()

        try:
            assert locked.wait(timeout=5), (
                "Worker did not acquire lock"
            )

            worker.start()

            assert started.wait(timeout=5), (
                "Reconciliation worker did not start"
            )

            assert not finished.wait(timeout=0.3), (
                "Reconciliation finished while lock was held"
            )

            release.set()

            assert finished.wait(timeout=5), (
                "Reconciliation did not finish after lock release"
            )

            assert not errors, f"Reconciliation errors: {errors}"
            assert results == ["in_sync"]

        finally:
            release.set()
            process.join(timeout=5)

            if process.is_alive():
                process.terminate()
                process.join(timeout=5)

            if worker.ident is not None:
                worker.join(timeout=5)

        assert process.exitcode == 0
        assert not worker.is_alive()

    finally:
        if project_id is not None:
            cleanup_reconciliation_data(
                engine, project_id, application_id
            )

        engine.dispose()


def test_reconciliation_blocks_until_lock_is_released(tmp_path):
    engine = create_engine(TEST_DATABASE_URL, pool_pre_ping=True)

    project_id = None
    application_id = None

    try:
        project_id, application_id = prepare_reconciliation_data(
            engine, tmp_path
        )

        context = multiprocessing.get_context("spawn")
        locked = context.Event()
        release = context.Event()

        process = context.Process(
            target=hold_gitops_lock,
            args=(str(tmp_path), project_id, locked, release),
        )

        process.start()

        try:
            assert locked.wait(timeout=5), (
                "Worker did not acquire lock"
            )

            lock_path = (
                tmp_path
                / ".locks"
                / f"staging--{project_id}--reconciliation-api.lock"
            )

            with lock_path.open("a+") as lock_file:
                try:
                    fcntl.flock(
                        lock_file.fileno(),
                        fcntl.LOCK_EX | fcntl.LOCK_NB,
                    )
                except BlockingIOError:
                    lock_is_held = True
                else:
                    lock_is_held = False
                    fcntl.flock(
                        lock_file.fileno(),
                        fcntl.LOCK_UN,
                    )

            assert lock_is_held, (
                "Expected project-specific GitOps lock to be held"
            )

            release.set()

            with Session(engine) as db:
                result = check_deployment_drift(
                    db=db,
                    application_id=application_id,
                    environment="staging",
                    gitops_root=tmp_path,
                )

            assert result == "in_sync"

        finally:
            release.set()
            process.join(timeout=5)

            if process.is_alive():
                process.terminate()
                process.join(timeout=5)

        assert process.exitcode == 0

    finally:
        if project_id is not None:
            cleanup_reconciliation_data(
                engine, project_id, application_id
            )

        engine.dispose()
