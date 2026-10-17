
import os
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import event, create_engine, text
from sqlalchemy.orm import Session

from afterpush_api.main import app, get_db
from afterpush_api.models import Application, Base, Deployment


TEST_DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL",
    "postgresql+psycopg://afterpush:afterpush_local_dev@127.0.0.1:5432/afterpush_test",
)

if TEST_DATABASE_URL.rsplit("/", 1)[-1] != "afterpush_test":
    raise RuntimeError(
        "Tests must use the afterpush_test database"
    )


@event.listens_for(Session, "before_flush")
def populate_deployment_snapshots_for_legacy_fixtures(session, *_):
    """Keep focused legacy fixtures valid under the snapshot schema.

    Production deployments are created by create_versioned_deployment.
    Older tests construct Deployment rows directly to exercise unrelated
    behavior, so this test-only adapter supplies the same snapshot values.
    """
    for deployment in session.new:
        if not isinstance(deployment, Deployment):
            continue

        if all(
            value is not None
            for value in (
                deployment.image_repository,
                deployment.port,
                deployment.replicas,
            )
        ):
            continue

        application = session.get(Application, deployment.application_id)

        if application is None:
            raise RuntimeError(
                "Deployment test fixture requires an application snapshot."
            )

        deployment.image_repository = application.image
        deployment.port = application.port
        deployment.replicas = application.replicas


@pytest.fixture
def db_session():
    """
    Provide an isolated PostgreSQL schema for each test.

    Existing public schema data is never modified.
    """
    schema = f"test_{uuid4().hex}"

    admin_engine = create_engine(TEST_DATABASE_URL)

    with admin_engine.begin() as connection:
        connection.execute(
            text(f'CREATE SCHEMA "{schema}"')
        )

    engine = create_engine(
        TEST_DATABASE_URL,
        connect_args={
            "options": f"-csearch_path={schema}"
        },
    )

    try:
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
        engine.dispose()

        with admin_engine.begin() as connection:
            connection.execute(
                text(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE')
            )

        admin_engine.dispose()


@pytest.fixture
def client(db_session):
    """
    Provide a FastAPI test client using the isolated
    PostgreSQL test session.
    """

    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    try:
        with TestClient(app) as test_client:
            yield test_client
    finally:
        app.dependency_overrides.pop(get_db, None)
