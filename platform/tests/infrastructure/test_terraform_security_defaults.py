from pathlib import Path
import re


PROJECT_ROOT = Path(__file__).resolve().parents[3]
EKS_ROOT = PROJECT_ROOT / "terraform/eks"
PRIMARY_ROOT = PROJECT_ROOT / "terraform"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_eks_profile_keeps_private_access_and_limits_temporary_public_access_to_one_operator_cidr():
    cluster = _read(EKS_ROOT / "eks.tf")
    variables = _read(EKS_ROOT / "variables.tf")

    assert "endpoint_private_access = true" in cluster
    assert "endpoint_public_access = true" in cluster
    assert "public_access_cidrs" in cluster
    assert "var.temporary_operator_public_access_cidrs" in cluster
    assert "temporary_operator_public_access_cidrs" in variables
    assert "length(var.temporary_operator_public_access_cidrs) == 1" in variables
    assert 'endswith(cidr, "/32")' in variables
    assert "requires Kubernetes 1.28 or later" in variables
    assert 'default     = "1.36"' in variables
    assert "encryption_config" not in cluster


def test_public_node_addresses_are_an_explicit_documented_topology_tradeoff():
    networking = _read(EKS_ROOT / "networking.tf")
    documentation = _read(EKS_ROOT / "README.md")

    assert networking.count("map_public_ip_on_launch = true") == 2
    assert networking.count('"kubernetes.io/role/internal-elb"') == 2
    assert "managed node group currently runs in the two public subnets" in documentation
    assert "NAT gateways or\ninterface endpoints" in documentation


def test_legacy_alb_defaults_to_internal_tls_only_with_explicit_public_controls():
    load_balancing = _read(PRIMARY_ROOT / "loadbalancing.tf")
    security = _read(PRIMARY_ROOT / "security.tf")
    variables = _read(PRIMARY_ROOT / "variables.tf")

    assert 'default     = "internal"' in variables
    assert re.search(
        r"internal\s+=\s+var\.alb_access_mode == \"internal\"",
        load_balancing,
    )
    assert "resource \"aws_lb_listener\" \"http\"" not in load_balancing
    assert "resource \"aws_lb_listener\" \"https\"" in load_balancing
    assert 'protocol          = "HTTPS"' in load_balancing
    assert "certificate_arn   = var.acm_certificate_arn" in load_balancing
    assert "public_alb_ingress_cidrs" in load_balancing
    assert "cidr_ipv4   = each.value" in security
    assert "0.0.0.0/0" not in security


def test_alert_topic_uses_a_scoped_rotation_enabled_customer_managed_key():
    monitoring = _read(PRIMARY_ROOT / "monitoring.tf")

    assert 'resource "aws_kms_key" "alerts"' in monitoring
    assert "enable_key_rotation     = true" in monitoring
    assert 'resource "aws_kms_alias" "alerts"' in monitoring
    assert "kms_master_key_id = aws_kms_key.alerts.arn" in monitoring
    assert "AllowSnsForThisTopic" in monitoring
    assert "kms:EncryptionContext:aws:sns:topicArn" in monitoring
    assert "AllowTarget5xxAlarmToPublish" in monitoring
    assert 'identifiers = ["cloudwatch.amazonaws.com"]' in monitoring
