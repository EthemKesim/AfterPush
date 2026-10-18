import os
import subprocess
import sys
from pathlib import Path
from uuid import uuid4

from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

from conftest import TEST_DATABASE_URL


PLATFORM_ROOT = Path(__file__).parents[2]


def test_alembic_upgrade_to_head_in_isolated_afterpush_test_schema():
    """Exercise the full Alembic upgrade path without touching public schema."""
    schema = f"migration_smoke_{uuid4().hex}"
    admin_engine = create_engine(TEST_DATABASE_URL)
    migration_url = make_url(TEST_DATABASE_URL).update_query_dict(
        {"options": f"-csearch_path={schema}"}
    )
    config = Config(str(PLATFORM_ROOT / "alembic.ini"))
    expected_revision = ScriptDirectory.from_config(config).get_current_head()

    try:
        with admin_engine.begin() as connection:
            connection.execute(text(f'CREATE SCHEMA "{schema}"'))

        result = subprocess.run(
            [sys.executable, "-m", "alembic", "-c", "alembic.ini", "upgrade", "head"],
            cwd=PLATFORM_ROOT,
            env={
                **os.environ,
                "DATABASE_URL": migration_url.render_as_string(hide_password=False),
            },
            capture_output=True,
            text=True,
        )

        assert result.returncode == 0, result.stderr
        assert "Running upgrade" in result.stderr

        with admin_engine.connect() as connection:
            revision = connection.execute(
                text(f'SELECT version_num FROM "{schema}".alembic_version')
            ).scalar_one()
            deployment_columns = connection.execute(
                text(
                    "SELECT column_name FROM information_schema.columns "
                    "WHERE table_schema = :schema AND table_name = 'deployments'"
                ),
                {"schema": schema},
            ).scalars().all()

        assert revision == expected_revision
        assert {
            "revision",
            "image_repository",
            "publication_claim_id",
            "publication_checked_at",
            "runtime_status",
            "promotion_source_deployment_id",
        } <= set(deployment_columns)
    finally:
        with admin_engine.begin() as connection:
            connection.execute(text(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE'))
        admin_engine.dispose()
