from uuid import uuid4

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from afterpush_api.database import DATABASE_URL
from afterpush_api.models import Base

from afterpush_api.models import Application, Deployment, Project
from afterpush_api.services.deployment_runtime_reconciliation import (
    reconcile_deployment_runtimes,
)
from afterpush_api.services.deployment_runtime_verification import (
    DeploymentRuntimeVerification,
)


@pytest.fixture
def db_session():
    """
    Isolate reconciliation tests from existing public-schema deployments.
    Each test receives its own PostgreSQL schema.
    """
    assert DATABASE_URL.split("?")[0].endswith("/afterpush_test")

    schema = f"test_reconcile_{uuid4().hex[:16]}"
    admin_engine = create_engine(DATABASE_URL)

    engine = None

    try:
        with admin_engine.begin() as connection:
            connection.execute(text(f'CREATE SCHEMA "{schema}"'))

        engine = create_engine(
            DATABASE_URL,
            connect_args={"options": f"-csearch_path={schema}"},
        )

        Base.metadata.create_all(engine)

        connection = engine.connect()
        transaction = connection.begin()
        session = Session(
            bind=connection,
            join_transaction_mode="create_savepoint",
        )

        try:
            yield session
        finally:
            session.close()
            transaction.rollback()
            connection.close()

    finally:
        if engine is not None:
            engine.dispose()

        try:
            with admin_engine.begin() as connection:
                connection.execute(
                    text(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE')
                )
        finally:
            admin_engine.dispose()


COMMIT_SHA = "a" * 40
REPOSITORY_URL = "git://afterpush-gitops-local:9418/afterpush.git"


class FakeObserver:
    def __init__(self, status="healthy", fail=False):
        self.status = status
        self.fail = fail
        self.requests = []

    def observe(self, request):
        self.requests.append(request)

        if self.fail:
            raise RuntimeError("Simulated Kubernetes failure")

        return DeploymentRuntimeVerification(
            status=self.status,
            reason=self.status,
            rollout_complete=self.status == "healthy",
            revision_verified=self.status == "healthy",
        )


def create_deployment(
    db,
    *,
    revision=1,
    status="published",
    application=None,
    application_name="reconcile-api",
):
    if application is None:
        project = Project(
            name=f"reconcile-project-{uuid4().hex[:12]}",
            repository_url="https://example.com/app.git",
        )
        db.add(project)
        db.flush()

        application = Application(
            project_id=project.id,
            name=application_name,
            image="nginx",
            port=80,
            replicas=1,
        )
        db.add(application)
        db.flush()

    deployment = Deployment(
        application_id=application.id,
        environment="dev",
        image_tag=f"v{revision}",
        revision=revision,
        status=status,
        published_commit_sha=COMMIT_SHA if status == "published" else None,
    )
    db.add(deployment)
    db.flush()

    return deployment


def test_worker_persists_healthy_status(db_session):
    deployment = create_deployment(db_session)
    observer = FakeObserver()

    result = reconcile_deployment_runtimes(
        db_session,
        observer=observer,
        repository_url=REPOSITORY_URL,
    )

    db_session.refresh(deployment)

    assert result == {
        "checked": 1,
        "updated": 1,
        "skipped": 0,
        "errors": 0,
    }
    assert deployment.runtime_status == "healthy"
    assert deployment.runtime_checked_at is not None
    assert observer.requests[0].expected_revision == 1


def test_worker_skips_old_revision(db_session):
    old = create_deployment(db_session)
    newer = create_deployment(
        db_session,
        revision=2,
        application=old.application,
    )
    observer = FakeObserver()

    result = reconcile_deployment_runtimes(
        db_session,
        observer=observer,
        repository_url=REPOSITORY_URL,
    )

    db_session.refresh(old)
    db_session.refresh(newer)

    assert result["checked"] == 1
    assert observer.requests[0].expected_revision == 2
    assert old.runtime_status == "unverified"
    assert newer.runtime_status == "healthy"


def test_worker_skips_when_new_revision_is_pending(db_session):
    old = create_deployment(db_session)
    create_deployment(
        db_session,
        revision=2,
        status="pending",
        application=old.application,
    )
    observer = FakeObserver()

    result = reconcile_deployment_runtimes(
        db_session,
        observer=observer,
        repository_url=REPOSITORY_URL,
    )

    assert result["checked"] == 0
    assert observer.requests == []


def test_worker_respects_limit(db_session):
    create_deployment(db_session)
    create_deployment(db_session)
    observer = FakeObserver()

    result = reconcile_deployment_runtimes(
        db_session,
        observer=observer,
        repository_url=REPOSITORY_URL,
        limit=1,
    )

    assert result["checked"] == 1
    assert result["updated"] == 1


def test_worker_records_observer_error(db_session):
    deployment = create_deployment(db_session)
    observer = FakeObserver(fail=True)

    result = reconcile_deployment_runtimes(
        db_session,
        observer=observer,
        repository_url=REPOSITORY_URL,
    )

    db_session.refresh(deployment)

    assert result["errors"] == 1
    assert result["updated"] == 0
    assert deployment.runtime_status == "unverified"
    assert deployment.runtime_reason == "observer_error"
    assert deployment.runtime_checked_at is not None


def test_observer_error_does_not_starve_an_unchecked_deployment(db_session):
    failed = create_deployment(
        db_session,
        application_name="failed-runtime-api",
    )

    reconcile_deployment_runtimes(
        db_session,
        observer=FakeObserver(fail=True),
        repository_url=REPOSITORY_URL,
        limit=1,
    )

    db_session.refresh(failed)
    assert failed.runtime_checked_at is not None

    create_deployment(
        db_session,
        application_name="unchecked-runtime-api",
    )
    observer = FakeObserver()

    result = reconcile_deployment_runtimes(
        db_session,
        observer=observer,
        repository_url=REPOSITORY_URL,
        limit=1,
    )

    assert result["updated"] == 1
    assert observer.requests[0].application_name == "unchecked-runtime-api"


def test_worker_persists_unverified_status(db_session):
    deployment = create_deployment(db_session)
    observer = FakeObserver(status="unverified")

    result = reconcile_deployment_runtimes(
        db_session,
        observer=observer,
        repository_url=REPOSITORY_URL,
    )

    db_session.refresh(deployment)

    assert result["updated"] == 1
    assert deployment.runtime_status == "unverified"
