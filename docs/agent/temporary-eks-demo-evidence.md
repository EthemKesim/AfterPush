# Temporary EKS demo and teardown evidence

Verification date: 2026-10-20 (Europe/Istanbul)
AWS account: `833090513321`
Region: `eu-central-1`
Cluster: `afterpush-eks`

This was a short-lived single-operator screenshot demo, not a
production-readiness claim. It reached the verified state below and was then
destroyed on 2026-10-20. This record does not assert that screenshots were
captured or that a live restore was tested.

## Infrastructure and access

- AWS identity was `arn:aws:iam::833090513321:user/launchforge-admin`.
- EKS cluster status: `ACTIVE`, Kubernetes `1.36`.
- Terraform remote state contained the expected 23 managed resources.
- A fresh Terraform plan with the single current operator IPv4 `/32` returned
  `No changes`.
- Both cluster subnets already had the `kubernetes.io/role/internal-elb` tag.
  No Terraform apply or subnet-tag change was needed.
- Public and private EKS API access are enabled; public API access is restricted
  to one operator `/32`.
- Managed node group `afterpush-eks-nodes`: one running `c7i-flex.large` node.
- No NAT Gateway or allocated Elastic IP was found for this demo VPC.
- An internal Application Load Balancer and one IP target group were present.

## GitOps and workload

- Temporary branch: `codex/temporary-eks-demo`.
- Branch head and Argo CD source revision at final healthy verification:
  `992f4da97450c52689a5d3df4a8649b4e3230a7e`.
- Initial workload deployment commit:
  `ca0d08e56c3a4551df4f74d446501ef022ca438d`.
- The Argo CD Application's chart and values sources both follow this temporary
  branch; `main` was not changed.
- `afterpush-api-eks`: `Synced`, `Healthy`.
- `metrics-server`: `Synced`, `Healthy`.
- Metrics APIService `v1beta1.metrics.k8s.io`: `Available=True`.
- API Deployment: `2/2` ready; both Pods `Running`.
- Service endpoints: two ready Pod IPs.
- HPA: 2 replicas, configured minimum 2 and maximum 5; CPU `3%/50%` at
  verification.
- Internal ALB target group: both API Pod targets `healthy`.
- Local service port-forward returned:

  ```json
  {"status":"ok","service":"afterpush-platform-api"}
  ```

- `/metrics` returned Prometheus metrics.

The temporary API manifest used `codex/temporary-eks-demo`; after teardown,
the repository manifest was restored to `main` so future GitOps restores use
the release branch. The EKS Terraform source was restored to its private-only
control-plane default. No temporary public `/32` was committed.

## Immutable image

- ECR repository: `afterpush-api` (`eu-central-1`).
- Tag: `temporary-eks-demo-dc5b434754`; repository tag mutability is
  `IMMUTABLE`.
- Digest: `sha256:39411062c22b7e9f0e133e0af075be8718313a1687e3a34e184bd6953726ed99`.
- Platform: `linux/amd64`; image user: UID `10001`.
- A local container `/health` smoke test succeeded before publication.
- ECR image-scan findings were unavailable (`ScanNotFoundException`); no clean
  vulnerability scan is claimed.

## Validation

- `terraform fmt -check -recursive terraform/eks`: passed.
- `terraform -chdir=terraform/eks validate`: passed.
- `platform/tests/infrastructure/test_terraform_security_defaults.py`:
  `4 passed`.
- `helm lint helm/afterpush -f gitops/apps/afterpush-api/values-eks.yaml`:
  passed (chart icon recommendation only).
- Helm template render: passed; internal ALB, non-root security context,
  immutable image tag, and HPA were present in rendered manifests.
- Docker image UID and `/health` smoke checks: passed.

## Teardown and remaining cost exposure

Before Terraform teardown, the `afterpush-api` Ingress was deleted through
Kubernetes. Its controller removed the internal ALB
`k8s-afterpus-afterpus-33c26d969e` and target group
`k8s-afterpus-afterpus-6cb49e323a`. AWS tags linked both to
`afterpush-eks` and `afterpush-dev/afterpush-api`. The Terraform plan was
reviewed as exactly `0 add, 0 change, 23 destroy`, then executed with the
guarded `scripts/aws-env.sh` stop command.

Post-teardown checks found no EKS cluster, running EC2 instance, EBS volume,
demo ALB/target group, demo VPC/subnet/Internet Gateway, NAT Gateway, or
allocated Elastic IP in `eu-central-1`. The EKS Terraform state is empty.
Shared state still has three managed resources. No Terraform state or ECR
image was deleted.

The requested snapshot ID `snap-026638e6765e0067c` was not found in
`eu-central-1`. The verified PostgreSQL recovery snapshot
`snap-04c0bf420fd3f6715` remains `completed`, encrypted, 5 GiB, and sourced
from `vol-029214c0cf7f20222`. Its restore has not been tested.

Three ECR repositories remain with 15 image manifests; their reported
`imageSizeInBytes` sum is 777,307,835 bytes (about 0.724 GiB before layer
deduplication). The versioned Terraform S3 bucket retains 164 object versions
with 2,635,331 bytes reported across those versions; the current EKS state
object is 476 bytes and server-side encrypted. These assets can incur storage
charges.

One CloudWatch log group, `/vpc/afterpush/flow-logs`, remains with 1,311 bytes,
no tags, and no retention policy. The Terraform source defines a 30-day policy,
but the live group has no configured expiry. No active VPC Flow Log producer
was found. It was not deleted because it is outside the EKS state root and its
audit-retention need has not been confirmed.

Cost Explorer's available 2026-10-01 through 2026-10-19 account-level data
showed `$46.8076168713` Usage and `-$46.8076169982` Credit. It is delayed,
not resource-attributed, and does not prove a zero bill. A rough retained
storage-only estimate is about `$0.25–$0.33/month` before traffic, requests,
regional price differences, and snapshot incremental-block accounting. The
snapshot, ECR, S3 history, and log-group storage are the remaining known
AfterPush storage exposures; active demo compute/networking charges were
removed.
