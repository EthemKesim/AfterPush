
import os

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from afterpush_api.main import app, get_db


TEST_DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL",
    "postgresql+psycopg://afterpush:afterpush_local_dev@127.0.0.1:5432/afterpush_test",
)

if TEST_DATABASE_URL.rsplit("/", 1)[-1] != "afterpush_test":
    raise RuntimeError(
        "Tests must use the afterpush_test database"
    )


@pytest.fixture
def db_session():
    """
    Provide an isolated PostgreSQL session for each test.

    Changes are rolled back after the test finishes.
    """

    engine = create_engine(TEST_DATABASE_URL)

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
        engine.dispose()


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
