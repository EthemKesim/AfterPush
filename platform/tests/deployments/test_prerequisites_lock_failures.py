from contextlib import contextmanager
from types import SimpleNamespace
from unittest.mock import MagicMock, Mock
from uuid import uuid4

import pytest

from afterpush_api.services.prerequisites_lock import (
    try_prerequisites_lock,
)


def make_connection(*, acquire=True, unlock=True):
    connection = Mock()
    connection.autocommit = False

    cursor = MagicMock()
    cursor.fetchone.side_effect = [
        (acquire,),
        (unlock,),
    ]

    cursor.__enter__.return_value = cursor
    connection.cursor.return_value = cursor

    engine = Mock()
    engine.raw_connection.return_value = connection

    return engine, connection, cursor


def test_unlock_failure_invalidates_connection():
    engine, connection, cursor = make_connection(unlock=False)

    with pytest.raises(RuntimeError, match="release failed"):
        with try_prerequisites_lock(
            engine=engine,
            project_id=uuid4(),
            environment="dev",
        ) as acquired:
            assert acquired is True

    connection.invalidate.assert_called_once()
    connection.close.assert_called_once()


def test_successful_unlock_preserves_connection():
    engine, connection, cursor = make_connection()

    with try_prerequisites_lock(
        engine=engine,
        project_id=uuid4(),
        environment="dev",
    ) as acquired:
        assert acquired is True

    connection.invalidate.assert_not_called()
    connection.close.assert_called_once()


def test_lock_acquisition_failure_invalidates_connection():
    engine, connection, cursor = make_connection()

    cursor.execute.side_effect = ConnectionError(
        "PostgreSQL connection lost"
    )

    with pytest.raises(ConnectionError, match="connection lost"):
        with try_prerequisites_lock(
            engine=engine,
            project_id=uuid4(),
            environment="dev",
        ):
            pytest.fail("Reconciliation must not start")

    connection.invalidate.assert_called_once()
    connection.close.assert_called_once()


def test_busy_lock_does_not_invalidate_connection():
    engine, connection, cursor = make_connection(acquire=False)

    with try_prerequisites_lock(
        engine=engine,
        project_id=uuid4(),
        environment="dev",
    ) as acquired:
        assert acquired is False

    connection.invalidate.assert_not_called()
    connection.close.assert_called_once()
