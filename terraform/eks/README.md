# EKS security profile

The EKS root is deliberately separate from the primary and shared Terraform
state roots. It is an apply-time AWS configuration, not part of the local
demo.

## Private control-plane access

The secure default enables the private EKS API endpoint and disables the
public endpoint. Before applying it, provide a VPC-based administrative path,
such as a reviewed VPN, bastion host, or SSM-managed host. This repository does
not invent a public administrator CIDR or create an access path automatically.

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
