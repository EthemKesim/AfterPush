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
    / "c3d8e1f2a4b5_add_deployment_spec_snapshot.py"
)


def load_migration_module():
    spec = importlib.util.spec_from_file_location(
        "deployment_spec_snapshot_migration",
        MIGRATION_PATH,
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_migration_backfills_deployment_snapshot_in_isolated_schema():
    engine = create_engine(TEST_DATABASE_URL)
    schema = f"migration_{uuid4().hex}"

    try:
        with engine.begin() as connection:
            connection.execute(text(f'CREATE SCHEMA "{schema}"'))
            connection.execute(text(f'SET search_path TO "{schema}"'))
            connection.execute(
                text(
                    "CREATE TABLE applications ("
                    "id UUID PRIMARY KEY, image VARCHAR(500) NOT NULL, "
                    "port INTEGER NOT NULL, replicas INTEGER NOT NULL)"
                )
            )
            connection.execute(
                text(
                    "CREATE TABLE deployments ("
                    "id UUID PRIMARY KEY, application_id UUID NOT NULL)"
                )
            )

            application_id = uuid4()
            deployment_id = uuid4()
            connection.execute(
                text(
                    "INSERT INTO applications (id, image, port, replicas) "
                    "VALUES (:id, :image, :port, :replicas)"
                ),
                {
                    "id": application_id,
                    "image": "registry.example/orders",
                    "port": 3000,
                    "replicas": 2,
                },
            )
            connection.execute(
                text(
                    "INSERT INTO deployments (id, application_id) "
                    "VALUES (:id, :application_id)"
                ),
                {"id": deployment_id, "application_id": application_id},
            )

            context = MigrationContext.configure(connection)
            migration = load_migration_module()

            with Operations.context(context):
                migration.upgrade()

            row = connection.execute(
                text(
                    "SELECT image_repository, port, replicas "
                    "FROM deployments WHERE id = :id"
                ),
                {"id": deployment_id},
            ).one()

            assert row == ("registry.example/orders", 3000, 2)

            nullable = connection.execute(
                text(
                    "SELECT is_nullable FROM information_schema.columns "
                    "WHERE table_schema = :schema AND table_name = 'deployments' "
                    "AND column_name = 'image_repository'"
                ),
                {"schema": schema},
            ).scalar_one()
            assert nullable == "NO"
    finally:
        with engine.begin() as connection:
            connection.execute(text(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE'))
        engine.dispose()
