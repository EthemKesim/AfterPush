from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from uuid import uuid4

from sqlalchemy import create_engine, delete
from sqlalchemy.orm import Session

from afterpush_api.models import Application, Deployment, Project
from afterpush_api.services.deployment_worker import (
    process_pending_deployments,
)
from afterpush_api.services.gitops import get_values_path
from conftest import TEST_DATABASE_URL


def test_parallel_workers_process_deployment_once(tmp_path):
    engine = create_engine(
        TEST_DATABASE_URL,
        pool_pre_ping=True,
    )

    project_id = None
    application_id = None

    try:
        with Session(engine) as db:
            project = Project(
                name=f"parallel-worker-{uuid4().hex[:8]}",
                repository_url="https://github.com/example/test",
            )
            db.add(project)
            db.flush()

            application = Application(
                project_id=project.id,
                name="parallel-service",
                image="nginx",
                port=3000,
                replicas=2,
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
                barrier.wait(timeout=10)

                return process_pending_deployments(
                    db=db,
                    gitops_root=tmp_path,
                    limit=20,
                )

        with ThreadPoolExecutor(max_workers=2) as executor:
            futures = [
                executor.submit(worker)
                for _ in range(2)
            ]

            results = [
                future.result(timeout=15)
                for future in futures
            ]

        total_applied = sum(
            result["applied"]
            for result in results
        )

        assert total_applied == 1

        assert sum(
            result["errors"]
            for result in results
        ) == 0

        with Session(engine) as db:
            saved = db.get(Deployment, deployment_id)
            assert saved.status == "running"

        values_path = get_values_path(
            gitops_root=tmp_path,
            application_name="parallel-service",
            environment="staging",
            project_id=project_id,
        )

        assert values_path.is_file()

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
