# EKS security profile

The EKS root is deliberately separate from the primary and shared Terraform
state roots. It is an apply-time AWS configuration, not part of the local
demo.

## Control-plane access

Private EKS API access is always enabled. The normal profile should keep the
public endpoint disabled and use a VPC-based administrative path, such as a
reviewed VPN, bastion host, or SSM-managed host.

For the explicitly approved, short-lived single-operator screenshot demo, the
root also supports public API access restricted to **exactly one** operator
IPv4 `/32` through `temporary_operator_public_access_cidrs`. Terraform rejects
an empty list, multiple CIDRs, and broader networks. The real address is local
operator input, is ignored by Git, and must be removed again during teardown.
It must never be changed to `0.0.0.0/0`.

## Kubernetes API-data encryption

The profile requires Kubernetes 1.28 or newer. Amazon EKS provides default
envelope encryption for all Kubernetes API data at that version and later,
using an AWS-owned KMS key unless an operator intentionally supplies a
customer-managed key. The older `encryption_config` pattern is deprecated for
this version range, so it is intentionally not added merely to satisfy a
static scanner. See the final validation report for the scanner limitation and
the required live verification boundary.

## Node subnet trade-off

The managed node group currently runs in the two public subnets, and those
subnets assign public IPv4 addresses on launch. That setting is required by
the present bootstrap topology: the nodes need outbound access for EKS and
image pulls, while this root intentionally does not create NAT gateways or
interface endpoints with recurring cost.

Moving nodes to private subnets is a future networking design change. It must
include a reviewed NAT or VPC-endpoint path and should be applied only after a
cost and connectivity decision. The setting is therefore a documented
conditional risk, not a claim that private node networking has been verified.

## Conditional risk acceptance

On 2026-10-19, the repository owner accepted this public-node-subnet trade-off
only for a personal, temporary, single-operator AWS test, demo, and portfolio
environment. It is not an approval for production, public SaaS, multi-tenant
use, sensitive data, long-running infrastructure, or unrestricted internet
exposure.

The acceptance covers `aws_subnet.public_a` and `aws_subnet.public_b`, which
assign public IPv4 addresses, and `aws_eks_node_group.main`, which uses those
subnets. It does not turn the finding into a claim that a live cluster has
been secured or verified.

### Controls enforced by source configuration

- Private EKS Kubernetes API access remains enabled. A public endpoint is
  allowed only for the approved temporary demo, and only for the single `/32`
  supplied at apply time.
- This root does not configure `remote_access` or an SSH key for the managed
  node group.
- The EKS GitOps values express an internal ALB and a `ClusterIP` platform
  Service. They are desired-state controls, not proof of a live ALB or CNI
  result.

### Operator conditions before any live use

- Verify the account, region, ownership, resulting EKS-managed cluster/node
  security groups, and that no unnecessary inbound node service or management
  path is exposed. The generated EKS security groups are not declared in this
  Terraform root, so this must be checked after an approved apply.
- Keep the environment temporary and single-operator; do not place sensitive
  data in it. Use a separately reviewed private-node design for any broader or
  longer-lived use.
- For the normal private-only profile, confirm a private administrator path for
  the EKS API (for example VPN, bastion, or SSM). The temporary `/32` exception
  is limited to the approved screenshot demo and is removed during teardown.

The acceptance must be reviewed again before production use, public exposure,
multi-user access, sensitive-data processing, a topology change, or extending
the environment beyond a short-lived demo. The final validation report records
the complete decision and the distinction between configuration evidence and
live verification.
