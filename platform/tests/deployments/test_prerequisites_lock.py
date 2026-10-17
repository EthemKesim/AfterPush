from uuid import uuid4

import pytest
from sqlalchemy import create_engine

from afterpush_api.services.prerequisites_lock import (
    prerequisites_lock_key,
    try_prerequisites_lock,
)
from conftest import TEST_DATABASE_URL


def test_lock_key_is_stable_and_scoped():
    project_id = uuid4()

    first = prerequisites_lock_key(
        project_id=project_id,
        environment="dev",
    )

    second = prerequisites_lock_key(
        project_id=project_id,
        environment="dev",
    )

    different_environment = prerequisites_lock_key(
        project_id=project_id,
        environment="prod",
    )

    assert first == second
    assert first != different_environment
    assert -(2**63) <= first < 2**63


def test_second_connection_cannot_acquire_same_lock():
    assert TEST_DATABASE_URL.rsplit("/", 1)[-1] == "afterpush_test"

    engine = create_engine(
        TEST_DATABASE_URL,
        pool_size=3,
        max_overflow=0,
    )

    project_id = uuid4()

    try:
        with try_prerequisites_lock(
            engine=engine,
            project_id=project_id,
            environment="dev",
        ) as first:
            assert first is True

            with try_prerequisites_lock(
                engine=engine,
                project_id=project_id,
                environment="dev",
            ) as second:
                assert second is False

        with try_prerequisites_lock(
            engine=engine,
            project_id=project_id,
            environment="dev",
        ) as third:
            assert third is True

    finally:
        engine.dispose()


def test_lock_is_released_after_exception():
    engine = create_engine(TEST_DATABASE_URL)

    project_id = uuid4()

    try:
        with pytest.raises(RuntimeError, match="test failure"):
            with try_prerequisites_lock(
                engine=engine,
                project_id=project_id,
                environment="dev",
            ) as acquired:
                assert acquired is True
                raise RuntimeError("test failure")

        with try_prerequisites_lock(
            engine=engine,
            project_id=project_id,
            environment="dev",
        ) as acquired:
            assert acquired is True

    finally:
        engine.dispose()
