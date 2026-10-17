"""PostgreSQL advisory locking for prerequisite reconciliation."""

import hashlib
from contextlib import contextmanager
from uuid import UUID


def prerequisites_lock_key(
    *,
    project_id: UUID,
    environment: str,
) -> int:
    """Create a stable signed 64-bit PostgreSQL advisory lock key."""

    identity = f"afterpush:prerequisites:{project_id}:{environment}"
    digest = hashlib.sha256(identity.encode("utf-8")).digest()

    return int.from_bytes(
        digest[:8],
        byteorder="big",
        signed=True,
    )


@contextmanager
def try_prerequisites_lock(
    *,
    engine,
    project_id: UUID,
    environment: str,
):
    """
    Hold a session-level PostgreSQL advisory lock during reconciliation.

    The connection uses autocommit so network operations do not keep
    a SQL transaction open.
    """

    key = prerequisites_lock_key(
        project_id=project_id,
        environment=environment,
    )

    connection = engine.raw_connection()
    acquired = False
    connection_safe = False

    try:
        connection.autocommit = True

        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT pg_try_advisory_lock(%s)",
                (key,),
            )
            acquired = bool(cursor.fetchone()[0])

        try:
            yield acquired
        finally:
            if acquired:
                with connection.cursor() as cursor:
                    cursor.execute(
                        "SELECT pg_advisory_unlock(%s)",
                        (key,),
                    )
                    unlocked = cursor.fetchone()[0]

                if unlocked is not True:
                    raise RuntimeError(
                        "PostgreSQL advisory lock release failed."
                    )

            connection_safe = True

    finally:
        try:
            if not connection_safe:
                connection.invalidate()
        finally:
            connection.close()
