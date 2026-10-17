import os
import subprocess
import sys


MODULE = "afterpush_api.workers.deployment_prerequisites"


def run_cli(*args, env=None):
    return subprocess.run(
        [sys.executable, "-m", MODULE, *args],
        env=env,
        capture_output=True,
        text=True,
        timeout=15,
    )


def test_requires_explicit_mode():
    result = run_cli()
    assert result.returncode == 2


def test_rejects_invalid_limit():
    result = run_cli("--dry-run", "--limit", "0")
    assert result.returncode == 2


def test_execute_is_disabled():
    result = run_cli("--execute")
    assert result.returncode == 2
    assert "--execute is disabled" in result.stderr


def test_dry_run_requires_database_url():
    env = os.environ.copy()
    env.pop("DATABASE_URL", None)

    result = run_cli("--dry-run", env=env)

    assert result.returncode == 2
    assert "DATABASE_URL must be explicitly configured" in result.stderr


def test_dry_run_rejects_non_test_database():
    env = os.environ.copy()
    env["DATABASE_URL"] = (
        "postgresql+psycopg://example:example@127.0.0.1:5432/afterpush"
    )

    result = run_cli("--dry-run", env=env)

    assert result.returncode == 2
    assert "restricted to afterpush_test" in result.stderr


def test_rejects_conflicting_kubernetes_options():
    result = run_cli(
        "--dry-run",
        "--in-cluster",
        "--kubeconfig-context",
        "example",
    )

    assert result.returncode == 2
