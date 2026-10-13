from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from uuid import uuid4

from sqlalchemy import create_engine, delete, text
from sqlalchemy.orm import Session

from afterpush_api.models import Application, Deployment, Project
from afterpush_api.services.deployment_orchestrator import apply_deployment
from afterpush_api.services.gitops import get_values_path
from conftest import TEST_DATABASE_URL


def test_two_workers_cannot_apply_same_deployment_twice(tmp_path):
    engine = create_engine(TEST_DATABASE_URL, pool_pre_ping=True)

    project_id = None
    application_id = None

    try:
        with Session(engine) as db:
            project = Project(
                name=f"worker-concurrency-{uuid4().hex[:8]}",
                repository_url="https://github.com/example/test",
            )
            db.add(project)
            db.flush()

            application = Application(
                project_id=project.id,
                name="concurrent-worker-service",
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
                db.execute(text("SET LOCAL lock_timeout = '5s'"))
                barrier.wait(timeout=10)

                return apply_deployment(
                    db=db,
                    deployment_id=deployment_id,
                    gitops_root=tmp_path,
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

        assert sorted(results) == [
            "applied",
            "invalid_status",
        ]

        with Session(engine) as db:
            saved = db.get(Deployment, deployment_id)
            assert saved.status == "running"

        values_path = get_values_path(
            gitops_root=tmp_path,
            application_name="concurrent-worker-service",
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
