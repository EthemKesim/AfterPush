from uuid import uuid4

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from afterpush_api.database import DATABASE_URL
from afterpush_api.models import Base, Application, Deployment, Project
from afterpush_api.services.deployment_runtime_reconciliation import (
    reconcile_deployment_runtimes_managed,
)
from afterpush_api.services.deployment_runtime_verification import (
    DeploymentRuntimeVerification,
)


COMMIT_SHA = "a" * 40
REPOSITORY_URL = "git://afterpush-gitops-local:9418/afterpush.git"


class FakeObserver:
    def __init__(self, fail=False):
        self.fail = fail
        self.calls = []

    def observe(self, request):
        self.calls.append(request)

        if self.fail:
            raise RuntimeError("Simulated Kubernetes failure")

        return DeploymentRuntimeVerification(
            status="healthy",
            reason="healthy",
            rollout_complete=True,
            revision_verified=True,
        )


@pytest.fixture
def managed_db():
    assert DATABASE_URL.split("?")[0].endswith("/afterpush_test")

    schema = f"test_runtime_{uuid4().hex[:16]}"
    admin_engine = create_engine(DATABASE_URL)

    with admin_engine.begin() as connection:
        connection.execute(text(f'CREATE SCHEMA "{schema}"'))

    engine = create_engine(
        DATABASE_URL,
        connect_args={"options": f"-csearch_path={schema}"},
    )
    factory = sessionmaker(bind=engine, expire_on_commit=False)

    try:
        Base.metadata.create_all(engine)

        with factory.begin() as db:
            project = Project(
                name=f"managed-{uuid4().hex[:12]}",
                repository_url="https://example.com/repo.git",
            )
            db.add(project)
            db.flush()

            application = Application(
                project_id=project.id,
                name="managed-api",
                image="nginx",
                port=80,
                replicas=1,
            )
            db.add(application)
            db.flush()

            deployment = Deployment(
                application_id=application.id,
                environment="dev",
                image_tag="v1",
                revision=1,
                status="published",
                published_commit_sha=COMMIT_SHA,
            )
            db.add(deployment)
            db.flush()
            deployment_id = deployment.id

        yield factory, deployment_id

    finally:
        engine.dispose()
        try:
            with admin_engine.begin() as connection:
                connection.execute(
                    text(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE')
                )
        finally:
            admin_engine.dispose()


def test_managed_worker_persists_runtime(managed_db):
    factory, deployment_id = managed_db
    observer = FakeObserver()

    result = reconcile_deployment_runtimes_managed(
        factory,
        observer=observer,
        repository_url=REPOSITORY_URL,
    )

    assert result == {
        "checked": 1,
        "updated": 1,
        "skipped": 0,
        "errors": 0,
    }
    assert len(observer.calls) == 1

    with factory() as db:
        deployment = db.get(Deployment, deployment_id)
        assert deployment.runtime_status == "healthy"
        assert deployment.runtime_checked_at is not None


def test_managed_worker_handles_observer_failure(managed_db):
    factory, deployment_id = managed_db
    observer = FakeObserver(fail=True)

    result = reconcile_deployment_runtimes_managed(
        factory,
        observer=observer,
        repository_url=REPOSITORY_URL,
    )

    assert result == {
        "checked": 0,
        "updated": 0,
        "skipped": 0,
        "errors": 1,
    }
    assert len(observer.calls) == 1

    with factory() as db:
        deployment = db.get(Deployment, deployment_id)
        assert deployment.runtime_status == "unverified"
        assert deployment.runtime_reason == "observer_error"
        assert deployment.runtime_checked_at is not None


def test_new_revision_blocks_stale_runtime_update(managed_db):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Event

    from afterpush_api.services.deployment_revision import (
        create_versioned_deployment,
    )
    from afterpush_api.services.deployment_runtime_persistence import (
        persist_deployment_runtime,
    )

    factory, deployment_id = managed_db

    with factory() as db:
        application_id = db.get(Deployment, deployment_id).application_id

    revision_created = Event()
    allow_commit = Event()

    def create_new_revision():
        with factory.begin() as db:
            new = create_versioned_deployment(
                db,
                application_id=application_id,
                environment="dev",
                image_tag="v2",
            )
            assert new is not None
            assert new.revision == 2

            revision_created.set()
            if not allow_commit.wait(timeout=10):
                raise TimeoutError("Timed out waiting to commit revision 2")

    def update_old_runtime():
        with factory.begin() as db:
            return persist_deployment_runtime(
                db,
                deployment_id=deployment_id,
                expected_commit_sha=COMMIT_SHA,
                expected_revision=1,
                verification=DeploymentRuntimeVerification(
                    status="healthy",
                    reason="healthy",
                    rollout_complete=True,
                    revision_verified=True,
                ),
            )

    with ThreadPoolExecutor(max_workers=2) as executor:
        creation = executor.submit(create_new_revision)

        assert revision_created.wait(timeout=10)

        runtime_update = executor.submit(update_old_runtime)

        # Revision 2 is committed before we inspect the result.
        allow_commit.set()

        creation.result(timeout=15)
        updated = runtime_update.result(timeout=15)

    assert updated is False

    with factory() as db:
        old = db.get(Deployment, deployment_id)
        assert old.runtime_status == "unverified"

        revisions = (
            db.query(Deployment.revision)
            .filter(Deployment.application_id == application_id)
            .order_by(Deployment.revision)
            .all()
        )
        assert [revision for (revision,) in revisions] == [1, 2]


def test_new_revision_blocks_stale_runtime_update(managed_db):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Event

    from afterpush_api.services.deployment_revision import (
        create_versioned_deployment,
    )
    from afterpush_api.services.deployment_runtime_persistence import (
        persist_deployment_runtime,
    )

    factory, deployment_id = managed_db

    with factory() as db:
        application_id = db.get(Deployment, deployment_id).application_id

    revision_created = Event()
    allow_commit = Event()

    def create_new_revision():
        with factory.begin() as db:
            new = create_versioned_deployment(
                db,
                application_id=application_id,
                environment="dev",
                image_tag="v2",
            )
            assert new is not None
            assert new.revision == 2

            revision_created.set()
            if not allow_commit.wait(timeout=10):
                raise TimeoutError("Timed out waiting to commit revision 2")

    def update_old_runtime():
        with factory.begin() as db:
            return persist_deployment_runtime(
                db,
                deployment_id=deployment_id,
                expected_commit_sha=COMMIT_SHA,
                expected_revision=1,
                verification=DeploymentRuntimeVerification(
                    status="healthy",
                    reason="healthy",
                    rollout_complete=True,
                    revision_verified=True,
                ),
            )

    with ThreadPoolExecutor(max_workers=2) as executor:
        creation = executor.submit(create_new_revision)

        assert revision_created.wait(timeout=10)

        runtime_update = executor.submit(update_old_runtime)

        # Revision 2 is committed before we inspect the result.
        allow_commit.set()

        creation.result(timeout=15)
        updated = runtime_update.result(timeout=15)

    assert updated is False

    with factory() as db:
        old = db.get(Deployment, deployment_id)
        assert old.runtime_status == "unverified"

        revisions = (
            db.query(Deployment.revision)
            .filter(Deployment.application_id == application_id)
            .order_by(Deployment.revision)
            .all()
        )
        assert [revision for (revision,) in revisions] == [1, 2]


def test_runtime_update_waits_for_application_lock(managed_db):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Event

    from sqlalchemy import text
    from sqlalchemy.exc import OperationalError

    from afterpush_api.services.deployment_revision import (
        create_versioned_deployment,
    )
    from afterpush_api.services.deployment_runtime_persistence import (
        persist_deployment_runtime,
    )

    factory, deployment_id = managed_db

    with factory() as db:
        application_id = db.get(Deployment, deployment_id).application_id

    lock_acquired = Event()
    release_lock = Event()

    def hold_application_lock():
        with factory.begin() as db:
            new = create_versioned_deployment(
                db,
                application_id=application_id,
                environment="dev",
                image_tag="v2",
            )
            assert new is not None
            assert new.revision == 2

            lock_acquired.set()

            if not release_lock.wait(timeout=10):
                raise TimeoutError("Application lock release timed out")

    def attempt_runtime_update():
        try:
            with factory.begin() as db:
                db.execute(text("SET LOCAL lock_timeout = '500ms'"))

                persist_deployment_runtime(
                    db,
                    deployment_id=deployment_id,
                    expected_commit_sha=COMMIT_SHA,
                    expected_revision=1,
                    verification=DeploymentRuntimeVerification(
                        status="healthy",
                        reason="healthy",
                        rollout_complete=True,
                        revision_verified=True,
                    ),
                )
        except OperationalError as exc:
            if getattr(exc.orig, "sqlstate", None) == "55P03":
                return "lock_timeout"
            raise

        return "unexpected_success"

    with ThreadPoolExecutor(max_workers=2) as executor:
        holder = executor.submit(hold_application_lock)

        assert lock_acquired.wait(timeout=10)

        contender = executor.submit(attempt_runtime_update)

        try:
            result = contender.result(timeout=5)
        finally:
            release_lock.set()

        holder.result(timeout=10)

    assert result == "lock_timeout"

    with factory() as db:
        old = db.get(Deployment, deployment_id)
        assert old.runtime_status == "unverified"

        revisions = (
            db.query(Deployment.revision)
            .filter(Deployment.application_id == application_id)
            .order_by(Deployment.revision)
            .all()
        )
        assert [revision for (revision,) in revisions] == [1, 2]
