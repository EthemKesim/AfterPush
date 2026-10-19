"""Local contracts for the cost-safe AWS operator entry point.

The tests use executable stand-ins. They never invoke a real AWS account,
Terraform backend, Kubernetes cluster, or database.
"""

from __future__ import annotations

from pathlib import Path
import subprocess
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[3]
CLI = PROJECT_ROOT / "scripts" / "aws_env.py"


def _run(*arguments: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(CLI), *arguments],
        cwd=PROJECT_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )


def _executable(path: Path, source: str) -> Path:
    path.write_text(source, encoding="utf-8")
    path.chmod(0o755)
    return path


def _fake_aws(path: Path, account: str) -> Path:
    return _executable(
        path,
        "#!/usr/bin/env python3\n"
        "import json, sys\n"
        "if 'get-caller-identity' in sys.argv:\n"
        f"    print(json.dumps({{'Account': '{account}'}}))\n"
        "else:\n"
        "    print('{}')\n",
    )


def _fake_terraform(
    path: Path,
    state_output: str,
    state_exit: int = 0,
    plan_exit: int = 0,
    apply_exit: int = 0,
) -> Path:
    return _executable(
        path,
        "#!/usr/bin/env python3\n"
        "import sys\n"
        "arguments = sys.argv[1:]\n"
        "if 'state' in arguments and 'list' in arguments:\n"
        f"    print({state_output!r})\n"
        f"    raise SystemExit({state_exit})\n"
        "if 'apply' in arguments:\n"
        f"    raise SystemExit({apply_exit})\n"
        "if 'plan' in arguments:\n"
        f"    raise SystemExit({plan_exit})\n"
        "raise SystemExit(0)\n",
    )


def test_status_is_safe_by_default_and_reports_inventory():
    result = _run("status")

    assert result.returncode == 0
    assert "safe preview" in result.stdout
    assert "LIVE AWS CHECK: not requested" in result.stdout
    assert "EKS cluster and managed nodes" in result.stdout
    assert "AfterPush cost inventory" in result.stdout


def test_stop_preview_never_requires_live_credentials():
    result = _run("stop", "--dry-run")

    assert result.returncode == 0
    assert "STOP preview" in result.stdout
    assert "No AWS, Kubernetes, Terraform backend, or remote state was contacted" in result.stdout


def test_execute_requires_exact_confirmation_and_expected_account():
    result = _run(
        "start",
        "--execute",
        "--account-id",
        "123456789012",
        "--profile",
        "test-profile",
    )

    assert result.returncode == 2
    assert "--confirm START" in result.stderr


def test_live_actions_require_an_explicit_profile_for_identity_consistency():
    result = _run(
        "verify",
        "--live",
        "--account-id",
        "123456789012",
    )

    assert result.returncode == 2
    assert "--profile is required" in result.stderr


def test_live_inventory_refuses_wrong_account(tmp_path: Path):
    aws = _fake_aws(tmp_path / "aws", "999999999999")

    result = _run(
        "verify",
        "--live",
        "--account-id",
        "123456789012",
        "--profile",
        "test-profile",
        "--aws-bin",
        str(aws),
    )

    assert result.returncode == 2
    assert "Refusing AWS account 999999999999" in result.stderr


def test_start_refuses_missing_terraform_state(tmp_path: Path):
    aws = _fake_aws(tmp_path / "aws", "123456789012")
    terraform = _fake_terraform(tmp_path / "terraform", "", state_exit=1)

    result = _run(
        "start",
        "--execute",
        "--confirm",
        "START",
        "--account-id",
        "123456789012",
        "--profile",
        "test-profile",
        "--targets",
        "eks",
        "--aws-bin",
        str(aws),
        "--terraform-bin",
        str(terraform),
    )

    assert result.returncode == 2
    assert "state for eks is unavailable" in result.stderr


def test_repeated_stop_is_a_safe_noop_when_state_is_empty(tmp_path: Path):
    aws = _fake_aws(tmp_path / "aws", "123456789012")
    terraform = _fake_terraform(tmp_path / "terraform", "")

    result = _run(
        "stop",
        "--execute",
        "--confirm",
        "STOP",
        "--account-id",
        "123456789012",
        "--profile",
        "test-profile",
        "--targets",
        "eks",
        "--data-recovery-confirmed",
        "--aws-bin",
        str(aws),
        "--terraform-bin",
        str(terraform),
    )

    assert result.returncode == 0
    assert "already empty; nothing to destroy" in result.stdout


def test_stop_refuses_shared_recovery_assets_even_with_execute(tmp_path: Path):
    aws = _fake_aws(tmp_path / "aws", "123456789012")

    result = _run(
        "stop",
        "--execute",
        "--confirm",
        "STOP",
        "--account-id",
        "123456789012",
        "--profile",
        "test-profile",
        "--targets",
        "shared",
        "--aws-bin",
        str(aws),
    )

    assert result.returncode == 2
    assert "shared is intentionally retained" in result.stderr


def test_start_restores_shared_before_eks_from_accessible_state(tmp_path: Path):
    aws = _fake_aws(tmp_path / "aws", "123456789012")
    terraform = _fake_terraform(tmp_path / "terraform", "aws_eks_cluster.main")

    result = _run(
        "start",
        "--execute",
        "--confirm",
        "START",
        "--account-id",
        "123456789012",
        "--profile",
        "test-profile",
        "--targets",
        "eks,shared",
        "--aws-bin",
        str(aws),
        "--terraform-bin",
        str(terraform),
    )

    assert result.returncode == 0
    assert result.stdout.index("shared: Terraform reports no changes") < result.stdout.index(
        "eks: Terraform reports no changes"
    )


def test_stop_accepts_data_sources_in_state_without_weakening_managed_resource_guard(tmp_path: Path):
    aws = _fake_aws(tmp_path / "aws", "123456789012")
    terraform = _fake_terraform(
        tmp_path / "terraform",
        "data.aws_availability_zones.available\naws_eks_cluster.main",
        plan_exit=2,
    )

    result = _run(
        "stop",
        "--execute",
        "--confirm",
        "STOP",
        "--account-id",
        "123456789012",
        "--profile",
        "test-profile",
        "--targets",
        "eks",
        "--data-recovery-confirmed",
        "--aws-bin",
        str(aws),
        "--terraform-bin",
        str(terraform),
    )

    assert result.returncode == 0
    assert "Terraform destroy completed from the reviewed plan" in result.stdout


def test_unknown_state_address_refuses_ownership_inference(tmp_path: Path):
    aws = _fake_aws(tmp_path / "aws", "123456789012")
    terraform = _fake_terraform(tmp_path / "terraform", "random_resource.unowned")

    result = _run(
        "stop",
        "--execute",
        "--confirm",
        "STOP",
        "--account-id",
        "123456789012",
        "--profile",
        "test-profile",
        "--targets",
        "eks",
        "--data-recovery-confirmed",
        "--aws-bin",
        str(aws),
        "--terraform-bin",
        str(terraform),
    )

    assert result.returncode == 2
    assert "ownership is uncertain" in result.stderr


def test_partially_provisioned_state_runs_a_state_backed_start_plan(tmp_path: Path):
    aws = _fake_aws(tmp_path / "aws", "123456789012")
    terraform = _fake_terraform(tmp_path / "terraform", "aws_eks_cluster.main", plan_exit=2)

    result = _run(
        "start",
        "--execute",
        "--confirm",
        "START",
        "--account-id",
        "123456789012",
        "--profile",
        "test-profile",
        "--targets",
        "eks",
        "--aws-bin",
        str(aws),
        "--terraform-bin",
        str(terraform),
    )

    assert result.returncode == 0
    assert "reviewed Terraform restore plan is ready" in result.stdout
    assert "Terraform restore completed from the reviewed plan" in result.stdout


def test_plan_failure_preserves_retry_boundary(tmp_path: Path):
    aws = _fake_aws(tmp_path / "aws", "123456789012")
    terraform = _fake_terraform(tmp_path / "terraform", "aws_eks_cluster.main", plan_exit=1)

    result = _run(
        "stop",
        "--execute",
        "--confirm",
        "STOP",
        "--account-id",
        "123456789012",
        "--profile",
        "test-profile",
        "--targets",
        "eks",
        "--data-recovery-confirmed",
        "--aws-bin",
        str(aws),
        "--terraform-bin",
        str(terraform),
    )

    assert result.returncode == 2
    assert "could not make a safe destroy plan" in result.stderr


def test_apply_failure_warns_that_state_may_be_partially_updated(tmp_path: Path):
    aws = _fake_aws(tmp_path / "aws", "123456789012")
    terraform = _fake_terraform(
        tmp_path / "terraform",
        "aws_eks_cluster.main",
        plan_exit=2,
        apply_exit=1,
    )

    result = _run(
        "stop",
        "--execute",
        "--confirm",
        "STOP",
        "--account-id",
        "123456789012",
        "--profile",
        "test-profile",
        "--targets",
        "eks",
        "--data-recovery-confirmed",
        "--aws-bin",
        str(aws),
        "--terraform-bin",
        str(terraform),
    )

    assert result.returncode == 2
    assert "State may reflect partial progress" in result.stderr
