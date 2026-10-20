# Temporary EKS demo evidence

Verification date: 2026-10-20 (Europe/Istanbul)
AWS account: `833090513321`
Region: `eu-central-1`
Cluster: `afterpush-eks`

This is a temporary screenshot demo, not a production-readiness claim. The
environment must remain running until the operator confirms screenshot capture.

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
- Branch head and Argo CD source revision at final verification:
  `c0f172899128ffb7f733974530d35b43a071a2f2`.
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

## Remaining AWS resources and cost exposure

The active demo includes the EKS control plane, one managed `c7i-flex.large`
worker, its 20 GiB gp3 root EBS volume, the demo VPC/subnets/Internet Gateway,
an automatically assigned public IPv4 address on the worker, and an internal
Application Load Balancer with a target group. EKS control-plane hours,
EC2 hours, public IPv4 hours, EBS storage, ALB hours/LCUs, and data transfer can
continue to incur charges. There is no NAT Gateway or allocated Elastic IP.
At published list rates, a rough 730-hour baseline is about `$169/month`:
approximately `$73` for standard-support EKS cluster hours, `$70.63` for the
worker, `$1.90` for its 20 GiB gp3 volume, `$3.65` for its in-use public IPv4,
and `$19.71` for the ALB hourly charge. This excludes ALB LCU usage, traffic,
logs, and other variable usage; it is not a bill or a credit-adjusted estimate.

The existing encrypted PostgreSQL recovery snapshot, Terraform state and
shared ECR repositories remain outside the demo cleanup scope and must be
preserved. The demo stays active until the operator confirms screenshot
completion; any later teardown requires a fresh plan and explicit approval.
