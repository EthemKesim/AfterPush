from concurrent.futures import ThreadPoolExecutor
from threading import Event
from types import SimpleNamespace
from unittest.mock import patch
from uuid import uuid4

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from afterpush_api.models import Application, Deployment
from afterpush_api.services.deployment_prerequisites_worker import (
    process_pending_prerequisites,
)
from conftest import TEST_DATABASE_URL


def test_two_workers_do_not_reconcile_same_project_environment():
    assert TEST_DATABASE_URL.rsplit("/", 1)[-1] == "afterpush_test"

    engine = create_engine(
        TEST_DATABASE_URL,
        pool_size=4,
        max_overflow=0,
    )

    project_id = uuid4()
    application_id = uuid4()
    deployment_id = uuid4()

    entered = Event()
    release = Event()

    deployment = SimpleNamespace(
        id=deployment_id,
        application_id=application_id,
        environment="dev",
        status="pending",
    )

    application = SimpleNamespace(
        id=application_id,
        project_id=project_id,
        name="concurrent-api",
    )

    def make_session():
        from unittest.mock import Mock

        db = Mock()

        def get_model(model, identifier):
            if model is Deployment:
                return deployment
            if model is Application:
                return application
            return None

        db.get.side_effect = get_model
        return db

    def blocking_reconciler(**kwargs):
        entered.set()

        if not release.wait(timeout=10):
            raise TimeoutError("First worker was not released")

        return SimpleNamespace(status="waiting")

    second_reconciler_calls = []

    def unexpected_reconciler(**kwargs):
        second_reconciler_calls.append(kwargs)
        return SimpleNamespace(status="ready")

    def run_worker(reconciler):
        db = make_session()

        return process_pending_prerequisites(
            db=db,
            repository_url="https://example.com/gitops.git",
            core_api=object(),
            rbac_api=object(),
            reconciler=reconciler,
            lock_engine=engine,
        )

    try:
        with (
            patch(
                "afterpush_api.services.deployment_prerequisites_worker."
                "get_pending_deployment_ids",
                return_value=[deployment_id],
            ),
            patch(
                "afterpush_api.services.deployment_prerequisites_worker."
                "is_deployment_prerequisites_eligible",
                return_value=True,
            ),
        ):
            with ThreadPoolExecutor(max_workers=2) as executor:
                first_future = executor.submit(
                    run_worker,
                    blocking_reconciler,
                )

                assert entered.wait(timeout=10), (
                    "First worker did not acquire the lock"
                )

                second_future = executor.submit(
                    run_worker,
                    unexpected_reconciler,
                )

                try:
                    second_result = second_future.result(timeout=10)
                finally:
                    release.set()

                first_result = first_future.result(timeout=10)

        assert first_result["waiting"] == 1
        assert first_result["errors"] == 0

        assert second_result["skipped"] == 1
        assert second_result["ready"] == 0
        assert second_result["errors"] == 0

        assert second_reconciler_calls == []

    finally:
        release.set()
        engine.dispose()
