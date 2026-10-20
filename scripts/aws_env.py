#!/usr/bin/env python3
"""Cost-safe, state-backed AWS operator workflow for AfterPush.

The CLI is intentionally conservative.  It never discovers-and-deletes AWS
resources by name.  A destructive action is limited to resources in one known
Terraform state root, needs an account/region check, an explicit command
confirmation, and a Terraform destroy plan.  All non-execute commands are
local previews unless --live is selected for AWS read-only inventory.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence


EXPECTED_REGION = "eu-central-1"
REQUIRED_SOURCE_PATHS = (
    "argocd/root-application.yaml",
    "argocd/eks/afterpush-api.yaml",
    "gitops/apps/afterpush-api/values-eks.yaml",
    "helm/afterpush/Chart.yaml",
    "platform/environments/eks/afterpush.yaml",
)


class OperatorError(RuntimeError):
    """A safety gate refused an operator action."""


@dataclass(frozen=True)
class TerraformRoot:
    key: str
    relative_path: str
    state_key: str
    purpose: str
    start_order: int
    stop_policy: str
    required_state_prefixes: tuple[str, ...]


ROOTS = {
    "shared": TerraformRoot(
        key="shared",
        relative_path="terraform/shared",
        state_key="afterpush/shared/terraform.tfstate",
        purpose="Persistent ECR repositories and GitHub OIDC delivery identity.",
        start_order=10,
        stop_policy="retain",
        required_state_prefixes=("aws_ecr_repository.", "aws_iam_role.github_actions_ecr"),
    ),
    "eks": TerraformRoot(
        key="eks",
        relative_path="terraform/eks",
        state_key="afterpush/eks-validation/terraform.tfstate",
        purpose="EKS cluster, managed nodes, VPC, IRSA roles, and EBS CSI addon.",
        start_order=20,
        stop_policy="destroy",
        required_state_prefixes=("aws_eks_cluster.main", "aws_vpc.eks"),
    ),
    "primary": TerraformRoot(
        key="primary",
        relative_path="terraform",
        state_key="afterpush/terraform.tfstate",
        purpose="Legacy ECS example, VPC, ALB, monitoring, and launchforge ECR.",
        start_order=30,
        stop_policy="manual-review",
        required_state_prefixes=("aws_vpc.main",),
    ),
}


STATIC_INVENTORY = (
    ("EKS cluster and managed nodes", "destroy", "eks", "Control-plane and EC2 capacity are recurring costs."),
    ("EKS VPC, subnets, route table, and internet gateway", "destroy", "eks", "Removed with the EKS root after dependent resources."),
    ("EBS CSI addon and EKS/IRSA IAM roles", "destroy", "eks", "Recreated from state-backed configuration."),
    ("ECR repository afterpush-api; shared configuration also defines afterpush-runtime-worker", "retain", "shared", "Retain images and OIDC-backed publishing. The runtime-worker repository is absent live and will be created from configuration during restore."),
    ("ECR repositories afterpush-platform-api and afterpush-platform-worker", "retain", "manual-review", "Retain existing platform images for recovery; these repositories are not managed by the shared Terraform state."),
    ("GitHub Actions ECR OIDC role", "retain", "shared", "Required for controlled image delivery after restore."),
    ("Legacy ECS, ALB, VPC endpoints, logs, alarms, SNS and KMS", "manual-review", "primary", "Separate legacy root; includes force-delete ECR and may retain data/cost."),
    ("Terraform S3 state bucket and lockfiles", "retain", "external", "State is required for safe recovery; never destroy through this tool."),
    ("Load balancers, EBS volumes, public IPv4/EIPs, Route 53 and DynamoDB", "manual-review", "external", "May be controller-created or manually created; verify ownership before action."),
)


def parse_args(argv: Sequence[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Cost-safe AfterPush AWS status/start/stop/verify workflow."
    )
    parser.add_argument("command", choices=("status", "start", "stop", "verify"))
    parser.add_argument(
        "--targets",
        help="Comma-separated Terraform roots. Defaults: start=shared,eks; stop=eks.",
    )
    parser.add_argument("--dry-run", action="store_true", help="Print intended work without AWS or Terraform backend access.")
    parser.add_argument("--execute", action="store_true", help="Permit a state-backed Terraform apply/destroy after all safety gates pass.")
    parser.add_argument("--live", action="store_true", help="Permit read-only AWS inventory for status or verify.")
    parser.add_argument("--confirm", help="Exact confirmation word: START or STOP.")
    parser.add_argument("--account-id", help="Expected AWS account ID; required for --live or --execute.")
    parser.add_argument("--region", default=os.environ.get("AWS_REGION", EXPECTED_REGION))
    parser.add_argument("--profile", default=os.environ.get("AWS_PROFILE"))
    parser.add_argument("--data-recovery-confirmed", action="store_true", help="Acknowledge PostgreSQL/secrets recovery review before EKS destroy.")
    parser.add_argument("--allow-legacy-root", action="store_true", help="Allow planning the separately reviewed legacy primary root.")
    parser.add_argument("--legacy-ecr-backup-confirmed", action="store_true", help="Acknowledge that the legacy root contains a force-delete ECR repository.")
    parser.add_argument("--aws-bin", default="aws", help=argparse.SUPPRESS)
    parser.add_argument("--terraform-bin", default="terraform", help=argparse.SUPPRESS)
    parser.add_argument("--repo-root", type=Path, default=Path(__file__).resolve().parents[1], help=argparse.SUPPRESS)
    args = parser.parse_args(argv)

    if args.dry_run and args.execute:
        parser.error("--dry-run and --execute cannot be used together.")
    if args.live and args.command not in {"status", "verify"}:
        parser.error("--live is for read-only status/verify; --execute is required for start/stop.")
    if args.execute and args.command not in {"start", "stop"}:
        parser.error("--execute is only valid for start or stop.")
    return args


def emit(message: str) -> None:
    print(message)


def run(command: Sequence[str], *, env: dict[str, str] | None = None, allow_failure: bool = False) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(command, text=True, capture_output=True, env=env, check=False)
    if result.returncode and not allow_failure:
        detail = (result.stderr or result.stdout or "command failed").strip()
        raise OperatorError(f"Command failed safely: {' '.join(command[:3])} … ({detail})")
    return result


def selected_roots(args: argparse.Namespace) -> list[TerraformRoot]:
    default = "shared,eks" if args.command == "start" else "eks"
    names = [name.strip() for name in (args.targets or default).split(",") if name.strip()]
    if not names:
        raise OperatorError("At least one Terraform target is required.")
    unknown = sorted(set(names) - set(ROOTS))
    if unknown:
        raise OperatorError(f"Unknown Terraform target(s): {', '.join(unknown)}.")
    return sorted((ROOTS[name] for name in dict.fromkeys(names)), key=lambda root: root.start_order)


def validate_source_layout(repo_root: Path) -> None:
    missing = [path for path in REQUIRED_SOURCE_PATHS if not (repo_root / path).is_file()]
    missing += [root.relative_path for root in ROOTS.values() if not (repo_root / root.relative_path / "backend.tf").is_file()]
    if missing:
        raise OperatorError("Required recovery source is missing: " + ", ".join(missing))


def validate_mode(args: argparse.Namespace) -> None:
    if args.region != EXPECTED_REGION:
        raise OperatorError(
            f"Refusing region {args.region!r}; this repository's configured state and default infrastructure region is {EXPECTED_REGION!r}."
        )
    if (args.live or args.execute) and not args.account_id:
        raise OperatorError("--account-id is required for any live AWS read or mutation.")
    if (args.live or args.execute) and not args.profile:
        raise OperatorError("--profile is required for any live AWS read or mutation so AWS CLI and Terraform use the same identity.")
    if args.execute:
        expected = "START" if args.command == "start" else "STOP"
        if args.confirm != expected:
            raise OperatorError(f"--execute requires --confirm {expected}.")


def aws_base(args: argparse.Namespace) -> list[str]:
    command = [args.aws_bin, "--no-cli-pager", "--region", args.region]
    if args.profile:
        command.extend(["--profile", args.profile])
    return command


def validate_aws_identity(args: argparse.Namespace) -> None:
    result = run([*aws_base(args), "sts", "get-caller-identity", "--output", "json"])
    try:
        account = json.loads(result.stdout)["Account"]
    except (json.JSONDecodeError, KeyError) as exc:
        raise OperatorError("AWS identity response did not contain an account ID.") from exc
    if account != args.account_id:
        raise OperatorError(f"Refusing AWS account {account}; expected {args.account_id}.")
    run([*aws_base(args), "ec2", "describe-availability-zones", "--all-availability-zones"])
    emit(f"AWS identity verified: account {account}, region {args.region}.")


def terraform_env(args: argparse.Namespace) -> dict[str, str]:
    environment = dict(os.environ)
    environment["AWS_REGION"] = args.region
    if args.profile:
        environment["AWS_PROFILE"] = args.profile
    return environment


def terraform_state(args: argparse.Namespace, root: TerraformRoot) -> list[str]:
    directory = args.repo_root / root.relative_path
    run([args.terraform_bin, "-chdir=" + str(directory), "init", "-input=false"], env=terraform_env(args))
    listed = run(
        [args.terraform_bin, "-chdir=" + str(directory), "state", "list"],
        env=terraform_env(args),
        allow_failure=True,
    )
    if listed.returncode:
        raise OperatorError(
            f"Terraform state for {root.key} is unavailable. Refusing to infer ownership or create a replacement state."
        )
    addresses = [line.strip() for line in listed.stdout.splitlines() if line.strip()]
    if any(
        not (address.startswith("aws_") or address.startswith("data."))
        for address in addresses
    ):
        raise OperatorError(f"Terraform state for {root.key} contains an unexpected address; ownership is uncertain.")
    return addresses


def terraform_variable_args(args: argparse.Namespace, root: TerraformRoot) -> list[str]:
    """Keep provider variables aligned with the identity preflight."""
    variables = [f"-var=aws_region={args.region}"]
    if root.key != "primary":
        variables.append(f"-var=aws_profile={args.profile}")
    return variables


def check_root_policy(args: argparse.Namespace, root: TerraformRoot) -> None:
    if root.key == "shared" and args.command == "stop":
        raise OperatorError("shared is intentionally retained: ECR images and GitHub OIDC are recovery assets.")
    if root.key == "primary":
        if not args.allow_legacy_root:
            raise OperatorError("primary is a legacy root. Use --allow-legacy-root only after reviewing its ECS/ALB/ECR lifecycle.")
        if args.command == "stop" and not args.legacy_ecr_backup_confirmed:
            raise OperatorError("primary stop requires --legacy-ecr-backup-confirmed because launchforge-api uses force_delete.")
    if root.key == "eks" and args.command == "stop" and not args.data_recovery_confirmed:
        raise OperatorError("EKS stop requires --data-recovery-confirmed; PostgreSQL/secrets recovery must be reviewed first.")


def terraform_plan(args: argparse.Namespace, root: TerraformRoot, *, destroy: bool) -> int:
    directory = args.repo_root / root.relative_path
    with tempfile.TemporaryDirectory(prefix="afterpush-terraform-plan-") as temporary:
        plan_path = Path(temporary) / f"{root.key}.tfplan"
        command = [
            args.terraform_bin,
            "-chdir=" + str(directory),
            "plan",
            "-input=false",
            "-detailed-exitcode",
            f"-out={plan_path}",
            *terraform_variable_args(args, root),
        ]
        if destroy:
            command.append("-destroy")
        planned = run(command, env=terraform_env(args), allow_failure=True)
        if planned.returncode not in {0, 2}:
            raise OperatorError(f"Terraform could not make a safe {'destroy' if destroy else 'start'} plan for {root.key}.")
        if planned.returncode == 0:
            emit(f"{root.key}: Terraform reports no changes; operation is already converged.")
            return 0
        emit(f"{root.key}: reviewed Terraform {'destroy' if destroy else 'restore'} plan is ready.")
        applied = run(
            [args.terraform_bin, "-chdir=" + str(directory), "apply", "-input=false", "-auto-approve", str(plan_path)],
            env=terraform_env(args),
            allow_failure=True,
        )
        if applied.returncode:
            raise OperatorError(
                f"{root.key}: Terraform apply did not complete. State may reflect partial progress; rerun status/verify and review the current state and plan before any retry."
            )
        emit(f"{root.key}: Terraform {'destroy' if destroy else 'restore'} completed from the reviewed plan.")
        return 2


def print_static_inventory() -> None:
    emit("\nAfterPush cost inventory (configuration evidence; not a live AWS claim):")
    for resource, decision, root, reason in STATIC_INVENTORY:
        emit(f"- [{decision.upper()}] {resource} ({root}): {reason}")


def print_recovery_boundary() -> None:
    emit("\nRecovery boundary:")
    emit("- GitOps/Helm/Argo CD source is validated locally, but Argo CD bootstrap and cluster rollout are not automated by this tool.")
    emit("- After EKS restore, use the reviewed disaster-recovery runbook from a private API access path; provide secrets out of band.")
    emit("- Runtime reconciliation remains suspended until image, Secret, ConfigMap, and scoped RBAC are reviewed.")


def live_inventory(args: argparse.Namespace) -> None:
    """Run only scoped read-only calls; failures become manual-review signals."""
    queries = (
        ("EKS clusters", ["eks", "list-clusters", "--output", "json"]),
        ("ECS clusters", ["ecs", "list-clusters", "--output", "json"]),
        ("VPC candidates", ["ec2", "describe-vpcs", "--filters", "Name=tag:Project,Values=afterpush,AfterPush", "--output", "json"]),
        ("subnet candidates", ["ec2", "describe-subnets", "--filters", "Name=tag:Project,Values=afterpush,AfterPush", "--output", "json"]),
        ("route table candidates", ["ec2", "describe-route-tables", "--filters", "Name=tag:Project,Values=afterpush,AfterPush", "--output", "json"]),
        ("security group candidates", ["ec2", "describe-security-groups", "--filters", "Name=tag:Project,Values=afterpush,AfterPush", "--output", "json"]),
        ("EC2 instances", ["ec2", "describe-instances", "--filters", "Name=tag:Project,Values=afterpush,AfterPush", "--output", "json"]),
        ("EBS volumes", ["ec2", "describe-volumes", "--filters", "Name=tag:Project,Values=afterpush,AfterPush", "--output", "json"]),
        ("EBS snapshots (account-owned; review ownership)", ["ec2", "describe-snapshots", "--owner-ids", "self", "--output", "json"]),
        ("NAT gateways", ["ec2", "describe-nat-gateways", "--filter", "Name=tag:Project,Values=afterpush,AfterPush", "--output", "json"]),
        ("Elastic IPs/public IPv4 candidates", ["ec2", "describe-addresses", "--output", "json"]),
        ("load balancer candidates", ["elbv2", "describe-load-balancers", "--output", "json"]),
        ("target group candidates", ["elbv2", "describe-target-groups", "--output", "json"]),
        ("ECR repositories (account-wide; review ownership)", ["ecr", "describe-repositories", "--output", "json"]),
        ("Terraform state bucket", ["s3api", "head-bucket", "--bucket", "afterpush-terraform-state-833090513321"]),
        ("CloudWatch log groups (account-wide; review ownership)", ["logs", "describe-log-groups", "--output", "json"]),
        ("CloudWatch alarms", ["cloudwatch", "describe-alarms", "--alarm-name-prefix", "afterpush", "--output", "json"]),
        ("SNS topics", ["sns", "list-topics", "--output", "json"]),
        ("KMS aliases", ["kms", "list-aliases", "--output", "json"]),
        ("Route 53 hosted zones", ["route53", "list-hosted-zones", "--output", "json"]),
    )
    emit("\nRead-only AWS inventory (candidates need ownership review):")
    for label, suffix in queries:
        result = run([*aws_base(args), *suffix], allow_failure=True)
        if result.returncode:
            emit(f"- [MANUAL REVIEW] {label}: unavailable or denied; no deletion was attempted.")
            continue
        try:
            payload = json.loads(result.stdout)
            count = sum(len(value) for value in payload.values() if isinstance(value, list))
        except json.JSONDecodeError:
            count = 0
        emit(f"- [READ ONLY] {label}: response received ({count} listed item(s)); confirm AfterPush ownership before action.")
    emit("- [RETAIN] Terraform state bucket: afterpush-terraform-state-833090513321 (presence/permissions must be checked through Terraform state preflight).")
    emit("- [MANUAL REVIEW] DynamoDB: no DynamoDB lock table is configured; this backend uses S3 lockfiles.")


def preview(args: argparse.Namespace, roots: list[TerraformRoot] | None = None) -> None:
    validate_source_layout(args.repo_root)
    if args.live:
        emit(
            f"Mode: read-only AWS inventory. Region contract: {EXPECTED_REGION}. "
            "AWS APIs are queried; no AWS resources, Terraform state, or Kubernetes objects are modified."
        )
    else:
        emit(f"Mode: safe preview. Region contract: {EXPECTED_REGION}. No AWS, Kubernetes, Terraform backend, or remote state was contacted.")
    if roots:
        emit("Targets: " + ", ".join(root.key for root in roots))
        for root in roots:
            emit(f"- {root.key}: {root.purpose} State key: {root.state_key}")
    print_static_inventory()
    print_recovery_boundary()


def start_or_stop(args: argparse.Namespace) -> None:
    roots = selected_roots(args)
    validate_source_layout(args.repo_root)
    if not args.execute:
        preview(args, roots)
        if args.command == "stop":
            emit("\nSTOP preview: only eks is destroy-eligible by default. shared is retained; primary requires extra legacy safeguards.")
        else:
            emit("\nSTART preview: shared precedes eks. Empty but accessible state means a deliberate stopped/initial lifecycle, not permission to invent another backend.")
        return

    validate_mode(args)
    validate_aws_identity(args)
    for root in roots:
        check_root_policy(args, root)
        addresses = terraform_state(args, root)
        if args.command == "stop" and not addresses:
            emit(f"{root.key}: state is accessible and already empty; nothing to destroy.")
            continue
        terraform_plan(args, root, destroy=args.command == "stop")
    if args.command == "start":
        print_recovery_boundary()
    else:
        emit("\nSTOP completed only for state-backed targets. Run `./scripts/aws-env.sh verify --live --account-id <account>` to review remaining costs.")


def status_or_verify(args: argparse.Namespace) -> None:
    validate_source_layout(args.repo_root)
    preview(args)
    if not args.live:
        emit("\nLIVE AWS CHECK: not requested. Use --live with --account-id for read-only inventory; it never deletes resources.")
        return
    validate_mode(args)
    validate_aws_identity(args)
    live_inventory(args)
    if args.command == "verify":
        emit("\nVERIFY result: this is an inventory, not a zero-cost billing guarantee. Review every candidate outside Terraform state manually.")


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    try:
        if args.command in {"start", "stop"}:
            start_or_stop(args)
        else:
            status_or_verify(args)
    except OperatorError as exc:
        print(f"SAFETY REFUSAL: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
