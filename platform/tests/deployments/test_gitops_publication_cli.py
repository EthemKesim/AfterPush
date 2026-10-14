import os
import subprocess
import sys


def test_cli_requires_gitops_repository_url():
    env = os.environ.copy()
    env.pop("AFTERPUSH_GITOPS_REPOSITORY_URL", None)

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "afterpush_api.workers.gitops_publication",
        ],
        env=env,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 2
    assert "AFTERPUSH_GITOPS_REPOSITORY_URL is required" in result.stderr


def test_cli_rejects_invalid_limit():
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "afterpush_api.workers.gitops_publication",
            "--limit",
            "0",
        ],
        capture_output=True,
        text=True,
    )

    assert result.returncode == 2
    assert "--limit must be greater than zero" in result.stderr
