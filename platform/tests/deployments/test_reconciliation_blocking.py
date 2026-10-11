
import multiprocessing
import os
import threading
from pathlib import Path
from uuid import UUID, uuid4

import yaml
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from afterpush_api.models import Application, Deployment, Project
from afterpush_api.services.deployment_reconciliation import (
    check_deployment_drift,
)
from afterpush_api.services.gitops import get_values_path
from afterpush_api.services.locking import gitops_application_lock


TEST_DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL",
    "postgresql+psycopg://afterpush:afterpush_local_dev@127.0.0.1:5432/afterpush_test",
)

if TEST_DATABASE_URL.rsplit("/", 1)[-1] != "afterpush_test":
    raise RuntimeError("Tests must use afterpush_test")


def hold_lock(
    root: str,
    application_name: str,
    project_id: UUID,
    locked,
    release,
):
    with gitops_application_lock(
        gitops_root=Path(root),
        application_name=application_name,
        environment="staging",
        project_id=project_id,
    ):
        locked.set()

        if not release.wait(timeout=10):
            raise TimeoutError("Lock release timed out")


def test_reconciliation_blocks_until_lock_released(tmp_path):
    engine = create_engine(TEST_DATABASE_URL)

    project_id = None
    application_id = None
    application_name = f"blocking-{uuid4().hex[:8]}"

    try:
        # Commit records so a separate session can read them.
        with Session(engine) as db:
            project = Project(
                name=f"blocking-project-{uuid4().hex[:8]}",
                repository_url="https://github.com/example/project",
            )
            db.add(project)
            db.flush()

            application = Application(
                project_id=project.id,
                name=application_name,
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
            application_name=application_name,
            environment="staging",
            project_id=project_id,
        )
        values_path.parent.mkdir(parents=True, exist_ok=True)

        with values_path.open("w", encoding="utf-8") as file:
            yaml.safe_dump(
                {
                    "image": {
                        "repository": "nginx",
                        "tag": "v2.0.0",
                    }
                },
                file,
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
            target=hold_lock,
            args=(
                str(tmp_path),
                application_name,
                project_id,
                locked,
                release,
            ),
        )

        worker = threading.Thread(
            target=reconciliation_worker,
            daemon=True,
        )

        process.start()

        try:
            assert locked.wait(timeout=5), (
                "Lock holder did not acquire the lock"
            )

            worker.start()

            assert started.wait(timeout=5), (
                "Reconciliation worker did not start"
            )

            # While the project's GitOps lock is held,
            # reconciliation must not complete.
            assert not finished.wait(timeout=0.3), (
                "Reconciliation finished while lock was held"
            )

            release.set()

            assert finished.wait(timeout=5), (
                "Reconciliation did not finish after release"
            )

            assert not errors, f"Worker errors: {errors}"
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
        # Clean up committed records in dependency order.
        if application_id is not None:
            with Session(engine) as db:
                db.query(Deployment).filter(
                    Deployment.application_id == application_id
                ).delete()

                db.query(Application).filter(
                    Application.id == application_id
                ).delete()

                if project_id is not None:
                    db.query(Project).filter(
                        Project.id == project_id
                    ).delete()

                db.commit()

        engine.dispose()
