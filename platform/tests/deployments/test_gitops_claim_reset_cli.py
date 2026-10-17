import subprocess
import sys
from uuid import uuid4

import pytest


def run_claim_reset(*arguments):
    return subprocess.run(
        [
            sys.executable,
            "-m",
            "afterpush_api.workers.gitops_claim_reset",
            *arguments,
        ],
        capture_output=True,
        text=True,
    )


def test_claim_reset_cli_requires_operator_confirmation():
    result = run_claim_reset(
        "--deployment-id",
        str(uuid4()),
        "--claim-id",
        str(uuid4()),
    )

    assert result.returncode == 2
    assert "--confirm-worker-stopped is required" in result.stderr


@pytest.mark.parametrize("argument", ["--deployment-id", "--claim-id"])
def test_claim_reset_cli_rejects_invalid_uuid(argument):
    arguments = [
        "--deployment-id",
        str(uuid4()),
        "--claim-id",
        str(uuid4()),
        "--confirm-worker-stopped",
    ]
    arguments[arguments.index(argument) + 1] = "not-a-uuid"

    result = run_claim_reset(*arguments)

    assert result.returncode == 2
    assert "invalid UUID value" in result.stderr


def test_claim_reset_cli_rejects_nonpositive_timeout():
    result = run_claim_reset(
        "--deployment-id",
        str(uuid4()),
        "--claim-id",
        str(uuid4()),
        "--confirm-worker-stopped",
        "--timeout-minutes",
        "0",
    )

    assert result.returncode == 2
    assert "--timeout-minutes must be at least 1" in result.stderr
