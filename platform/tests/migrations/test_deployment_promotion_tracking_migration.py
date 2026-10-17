import importlib.util
from pathlib import Path
from uuid import uuid4

from alembic.operations import Operations
from alembic.runtime.migration import MigrationContext
from sqlalchemy import create_engine, text

from conftest import TEST_DATABASE_URL


MIGRATION_PATH = (
    Path(__file__).parents[2]
    / "migrations"
    / "versions"
    / "f6c9d3e8a1b4_add_deployment_promotion_tracking.py"
)


def load_migration_module():
    spec = importlib.util.spec_from_file_location(
        "deployment_promotion_tracking_migration",
        MIGRATION_PATH,
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_migration_adds_promotion_link_and_approval_timestamp():
    engine = create_engine(TEST_DATABASE_URL)
    schema = f"migration_{uuid4().hex}"

    try:
        with engine.begin() as connection:
            connection.execute(text(f'CREATE SCHEMA "{schema}"'))
            connection.execute(text(f'SET search_path TO "{schema}"'))
            connection.execute(
                text("CREATE TABLE deployments (id UUID PRIMARY KEY)")
            )

            context = MigrationContext.configure(connection)
            migration = load_migration_module()
            with Operations.context(context):
                migration.upgrade()

            columns = connection.execute(
                text(
                    "SELECT column_name FROM information_schema.columns "
                    "WHERE table_schema = :schema AND table_name = 'deployments'"
                ),
                {"schema": schema},
            ).scalars().all()
            assert "promotion_source_deployment_id" in columns
            assert "approved_at" in columns

            indexes = connection.execute(
                text(
                    "SELECT indexname FROM pg_indexes "
                    "WHERE schemaname = :schema AND tablename = 'deployments'"
                ),
                {"schema": schema},
            ).scalars().all()
            assert "ix_deployments_promotion_source_deployment_id" in indexes
    finally:
        with engine.begin() as connection:
            connection.execute(text(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE'))
        engine.dispose()
