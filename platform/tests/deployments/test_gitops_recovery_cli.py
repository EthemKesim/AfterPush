import os
import subprocess
import sys

import pytest


@pytest.mark.parametrize(
    "argument,value",
    [
        ("--timeout-minutes", "0"),
        ("--limit", "0"),
    ],
)
def test_recovery_cli_rejects_invalid_arguments(argument, value):
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "afterpush_api.workers.gitops_recovery",
            argument,
            value,
        ],
        capture_output=True,
        text=True,
    )

    assert result.returncode == 2
    assert "must be at least 1" in result.stderr


def test_recovery_cli_requires_gitops_repository_url():
    env = os.environ.copy()
    env.pop("AFTERPUSH_GITOPS_REPOSITORY_URL", None)

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "afterpush_api.workers.gitops_recovery",
        ],
        env=env,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 2
    assert "AFTERPUSH_GITOPS_REPOSITORY_URL is required" in result.stderr
