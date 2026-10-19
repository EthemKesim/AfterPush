# Final validation and release-readiness review

**Review date:** 2026-10-19
**Repository baseline:** `main` at `3c14b7f` (merged PR #89)
**Review branch:** `codex/aws-cost-safe-operations`

This report records the final review evidence for the portfolio prototype. A
result marked PASS proves only the stated local, CI, or static scope; it does
not prove a live AWS/EKS deployment.

## Outcome summary

| Area | Outcome | Evidence type |
| --- | --- | --- |
| FastAPI platform tests | PASS | 834 passed across two local `afterpush_test` PostgreSQL groups |
| Legacy Node application | PASS | Local test, lint, build, dependency audit |
| Container builds and image scans | PASS | Local Docker and Trivy |
| Helm, GitOps, and Argo CD source checks | PASS | Offline lint, render, and static inspection |
| Terraform format and configuration validation | PASS | Backend-disabled temporary copies |
| Terraform security configuration | PASS — scoped acceptance | Static Trivy scan plus documented single-operator risk acceptance |
| AWS lifecycle safety tool | PASS — local/mock and live shutdown | Preview/guard tests plus state-backed EKS teardown; live restore not verified |
| GitHub Actions for the prior review branch | PASS | GitHub Actions run #173 |
| GitHub Actions before final repository changes | PASS | Earlier PR #90 head `758fd1d` had all three checks pass; consult PR #90 for current head status |
| Live AWS shutdown | PASS | EKS state empty; cluster, worker, VPC, and original PostgreSQL volume removed |
| Live AWS/EKS restore, Argo CD, and runtime reconciliation | NOT VERIFIED | No restore, sync, or post-restore health check was performed |

## Automated tests

### Platform control plane

**PASS** — the following command completed against the designated local test
database only:

```bash
DATABASE_URL=postgresql+psycopg://afterpush:afterpush_local_dev@127.0.0.1:5432/afterpush_test \
TEST_DATABASE_URL=postgresql+psycopg://afterpush:afterpush_local_dev@127.0.0.1:5432/afterpush_test \
platform/.venv/bin/python -m pytest \
  platform/tests/api platform/tests/demo platform/tests/engine \
  platform/tests/infrastructure platform/tests/migrations -q

DATABASE_URL=postgresql+psycopg://afterpush:afterpush_local_dev@127.0.0.1:5432/afterpush_test \
TEST_DATABASE_URL=postgresql+psycopg://afterpush:afterpush_local_dev@127.0.0.1:5432/afterpush_test \
platform/.venv/bin/python -m pytest \
  platform/tests/deployments platform/tests/gitops -q
```

Result: **834 passed** across two complete directory groups (506 and 328
tests), both against the same `afterpush_test` database. Each group reported
the existing Starlette `TestClient`/`httpx` deprecation warning. This suite
covers Alembic migration paths, deployment revisions and promotion,
prerequisite/namespace/RBAC gates, publication/recovery/stale-claim paths,
runtime reconciliation, GitOps integration, CLI validation/rendering, local
demo, and infrastructure and workflow contract tests.

Warning: Starlette's `TestClient` reports that its current `httpx` integration
is deprecated. It did not fail a test; dependency compatibility should be
reviewed when the test stack is upgraded.

### Legacy demo application

**PASS** — from `app/`:

```bash
npm test && npm run lint && npm run build && npm audit --audit-level=high
```

Result: **3 passed**; lint and TypeScript build succeeded; `npm audit` found
**0 vulnerabilities** at the HIGH/CRITICAL threshold. These checks were rerun
for the final repository changes. An initial sandboxed
test attempt could not bind a temporary local port (`EPERM`); the same test
passed in the permitted local execution environment, so that was an execution
environment limitation rather than an application failure.

### Local demo evidence

**PASS** — `afterpush validate`, `afterpush render`, and `afterpush deploy`
were run with `platform/examples/afterpush.yaml` and a temporary GitOps output
directory. The command validated the definition and generated
`afterpush-api/values.yaml`. The full platform suite above includes the local
journey and isolated temporary-bare-repository publication tests.

This is not evidence of a remote Git push, Argo CD synchronization, Kubernetes
rollout, or live runtime health.

## Containers and dependency security

**PASS within scanner scope.** The local images below built successfully:

| Image | Runtime check | User | HIGH/CRITICAL Trivy findings |
| --- | --- | --- | --- |
| `afterpush-legacy:m4` | `/health` returned healthy | `node` | 0 |
| `afterpush-platform-api:m4` | `/health` and `/metrics` succeeded | `10001` | 0 |
| `afterpush-runtime-worker:m4` | reconciliation worker `--help` succeeded | `10001` | 0 |

The legacy Dockerfile now uses the base image's non-root `node` user. Both
application and platform build contexts exclude `.env` files and private-key
patterns, reducing the chance that future local secrets enter a build context.

Trivy 0.74.0 used its current local vulnerability database and scanned the
Alpine base and language packages. A zero-finding result is not a guarantee
that an image has no vulnerability: it is limited to the scanner database,
selected HIGH/CRITICAL threshold, and image contents at review time. The
manually dispatched ECR workflow publishes commit-SHA tags and requests
provenance and SBOM; it uses GitHub OIDC instead of stored AWS access keys.

The review used these local commands (with distinct local-only image tags):

```bash
docker build -t afterpush-legacy:m4 app/
docker build --file platform/Dockerfile.api --tag afterpush-platform-api:m4 platform
docker build --file platform/Dockerfile.runtime-worker --tag afterpush-runtime-worker:m4 platform
trivy image --scanners vuln --severity HIGH,CRITICAL --ignore-unfixed=false <image>
```

## Helm, Kubernetes, Argo CD, and GitOps

**PASS for offline/static checks.** The following values files completed both
`helm lint` and `helm template` with `helm/afterpush`:

- `gitops/apps/afterpush-api/values-local.yaml`
- `gitops/apps/afterpush-api/values.yaml`
- `gitops/apps/afterpush-api/values-eks.yaml`

```bash
helm lint helm/afterpush -f <values-file>
helm template <release-name> helm/afterpush -f <values-file>
```

Rendered EKS output contains a ServiceAccount, Deployment, Service, HPA,
Ingress, resource requests/limits, `runAsNonRoot`, and a read-only root
filesystem. The EKS values set the unauthenticated platform API ALB scheme to
`internal`. The chart also renders a NetworkPolicy where enabled by values.

Argo CD application definitions referring to this repository use
`targetRevision: main`. They configure Argo CD to render the Helm chart with
Git-tracked values; Helm is not represented as an independent continuous
deployment controller. The runtime-reconciliation CronJob remains
`suspend: true` and requires its image, Secret, ConfigMap, and scoped RBAC to
be reviewed before activation.

**NOT VERIFIED:** a real cluster's admission behavior, NetworkPolicy/CNI
enforcement, ALB behavior, Argo CD synchronization, workload rollout, and
runtime-worker observation. The offline source checks did not contact a
cluster; the separately documented EKS shutdown was verified live.

## Terraform and AWS

### Syntax and state-boundary validation

**PASS** — `terraform fmt -check -recursive` passed. Each of `terraform/`,
`terraform/shared/`, and `terraform/eks/` was copied to an isolated temporary
directory, initialized with `terraform init -backend=false -input=false`, and
validated successfully. This avoided an existing local backend cache, did not
read remote state, and did not run plan, apply, destroy, refresh, or any AWS
operation.

```bash
terraform fmt -check -recursive
terraform -chdir=<clean-copy/root> init -backend=false -input=false
terraform -chdir=<clean-copy/root> validate
```

The static review confirms separate primary, shared (ECR/GitHub OIDC), and EKS
roots. The GitHub Actions OIDC trust is limited to the repository's `main`
branch, and its ECR policy scopes image-push actions to the two declared ECR
repositories (the required authorization-token action remains AWS-wide).

### Security configuration

**PASS for the explicitly accepted portfolio scope — no CRITICAL finding
remains.** This is not a production-security claim and does not prove a live
AWS/EKS deployment. Trivy 0.74.0 was run on an isolated copy of Terraform
source. The copy excluded local provider caches, untracked state/backup files,
and untracked `tfplan*` artifacts; none were modified or committed. This
avoids treating an old plan snapshot as current source configuration.

```bash
workdir=$(mktemp -d)
rsync -a --exclude '.terraform' --exclude '*.tfstate' \
  --exclude '*.tfstate.*' --exclude '*.tfplan' --exclude 'tfplan*' \
  terraform/ "$workdir/terraform/"
trivy config --severity HIGH,CRITICAL "$workdir/terraform"
```

| Check | Result | Decision and evidence |
| --- | --- | --- |
| AWS-0040 / AWS-0041 | RESOLVED | `terraform/eks/eks.tf` keeps private access on and explicitly sets `endpoint_public_access = false`; no administrator CIDR was invented. Operators need a reviewed VPC path such as VPN, bastion, or SSM before an apply. |
| AWS-0039 | SCANNER LIMITATION | EKS Kubernetes 1.36 is constrained to 1.28+. AWS documents default envelope encryption for all Kubernetes API data at 1.28+, with an AWS-owned KMS key. The older customer-managed `encryption_config` pattern is deprecated for this version range, so it was not added solely to silence Trivy. [AWS EKS envelope encryption](https://docs.aws.amazon.com/eks/latest/userguide/envelope-encryption.html) |
| AWS-0164 (two subnets) | ACCEPTED CONDITIONAL RISK | The managed node group still uses public subnets with automatic public IPv4 for bootstrap and image pulls. On 2026-10-19, the repository owner accepted this only for a personal, temporary, single-operator AWS test/demo/portfolio environment. It is excluded from production, public SaaS, multi-tenant, sensitive-data, long-running, or unrestricted-internet use. A private-node NAT/VPC-endpoint design remains required for those cases. |
| AWS-0054 | RESOLVED | The legacy ECS ALB has only an HTTPS listener using an operator-supplied ACM certificate; plaintext HTTP was removed. |
| AWS-0053 | RESOLVED | The legacy ECS ALB defaults to `internal`. Public mode requires an explicit selection and non-empty CIDR allowlist. |
| AWS-0136 | RESOLVED | The alerts topic now uses a rotation-enabled customer-managed KMS key. The key policy permits only account-root administration, the named SNS topic, and the named CloudWatch alarm's required KMS actions. |

The clean-source scan reported exactly one AWS-0039 HIGH finding and two
AWS-0164 HIGH findings; it reported **no CRITICAL findings**. The first is the
documented scanner limitation above. The second is a real design trade-off
accepted only under the scope and conditions below. Focused infrastructure
tests protect the private endpoint, modern-encryption assumption, explicit
public-node trade-off, TLS-only/internal ALB default, public allowlist guard,
SNS KMS key, and existing Terraform/CI state-boundary contracts.

### AWS-0164 risk-acceptance record

**Decision owner and date:** repository owner, 2026-10-19.

**Affected source:** `terraform/eks/networking.tf` defines
`aws_subnet.public_a` and `aws_subnet.public_b` with
`map_public_ip_on_launch = true`; `terraform/eks/eks.tf` places
`aws_eks_node_group.main` in those subnets.

**Accepted scope:** personal, temporary, single-operator AWS test/demo/
portfolio use. It is not accepted for production, public SaaS, multi-tenant
use, sensitive data, long-lived infrastructure, or unrestricted public
internet exposure.

| Control or condition | Classification | Evidence and boundary |
| --- | --- | --- |
| EKS Kubernetes API is not public | Enforced by source; live drift removed | Source tests require private-only access. The final live inventory found the old cluster open to `0.0.0.0/0`; that cluster was destroyed. A reviewed VPC-based administrator path is still needed before any restore. |
| Managed node group has no source-configured SSH remote access | Source configuration evidence | `aws_eks_node_group.main` contains no `remote_access` or SSH key. This absence is not proof of the live node security groups. |
| Platform API is intended to remain private | Enforced desired state | EKS GitOps values use an internal ALB and `ClusterIP` Service; Helm/source tests cover this. Actual ALB and CNI behavior were not exercised. |
| Node inbound exposure is restricted | Operational live-use requirement | Before any approved apply/use, inspect resulting EKS-managed cluster/node security groups and confirm there is no unnecessary inbound node service or management path. Those groups are not declared in this Terraform root. |
| Environment remains low-risk | Operational requirement | Keep it temporary and single-operator; do not use sensitive data. Verify account, region, and resource ownership before every live action. |

**Re-review triggers:** any production or public exposure, multi-user access,
sensitive-data use, a change to node/network topology, or extending this
beyond a short-lived demo. Such a change requires a separate security review
and, where appropriate, a costed private-node design using NAT gateways and/or
VPC endpoints. This acceptance does not authorize a live Terraform apply, EKS
operation, or data migration.

## Cost-safe shutdown and restore

**PASS for local safety behavior and live shutdown; live AWS/EKS restore remains
unverified.**
`scripts/aws-env.sh` exposes `status`, `start`, `stop`, and `verify`. Without
`--live` or `--execute`, each command is a source-only preview and does not
contact AWS, a Terraform backend, Kubernetes, or a database.

The normal lifecycle keeps `terraform/shared/` ECR repositories and the GitHub
OIDC role as recovery assets, protects the Terraform S3 state bucket, and
limits normal destroy eligibility to the EKS root. It refuses a destructive
operation unless the account ID and `eu-central-1` region match, remote state
is readable, state addresses establish ownership, the exact confirmation word
is supplied, and EKS teardown acknowledges data/secrets recovery. The legacy
primary root remains outside the normal stop path because it contains a
force-delete ECR repository; it needs separate legacy and image-backup
acknowledgements.

`verify --live` is deliberately read-only. It inventories EKS, EC2/EBS, ECS,
VPC/subnet/route/security-group candidates, NAT gateways, public IPv4/EIPs,
load balancers/target groups, ECR, state-bucket access, CloudWatch, SNS, KMS,
and Route 53, then marks any non-state-owned candidate for manual review. It
does not run a broad cleanup command and cannot prove that an AWS bill is zero.

The local contract suite covered safe preview, start confirmation, wrong AWS
account, missing state, repeated stop against an empty state, retained shared
assets, dependency ordering, partial-state planning, unknown ownership, and
plan-failure recovery boundaries. Final lifecycle and Terraform security
regression tests passed: **18 passed, 1 warning**. The complete affected
`platform/tests/infrastructure` suite passed: **426 passed, 1 warning**, using
only `afterpush_test`. The warning is the existing Starlette `TestClient`/
`httpx` deprecation warning.

The tool can recreate state-backed infrastructure from a reviewed Terraform
plan, but it does not bootstrap Argo CD or assert Kubernetes application
health. After a restored EKS cluster, the operator must use private API access,
provide secrets out of band, and follow the existing disaster-recovery runbook
to bootstrap Argo CD and observe GitOps reconciliation.

## Final live shutdown and cost audit

On 2026-10-19, `aws sts get-caller-identity --profile terraform` verified the
intended account and `eu-central-1` region. The `terraform/eks/` state contained
23 managed resources; a freshly generated plan was `0 add, 0 change, 23
destroy`, matching the previously reviewed scope. The first Terraform apply
partially completed: the EKS cluster, managed node group, and most EKS
resources were removed, but the Internet Gateway could not detach while
EKS-managed ENIs still had mapped public addresses. CloudTrail, current state,
and the remaining two-resource destroy plan were reviewed. After AWS removed
the ENIs, the same guarded lifecycle command completed the VPC/Internet
Gateway deletion. The final EKS state is empty and the shared and primary
states remain unchanged.

Direct post-shutdown AWS checks confirmed:

- No EKS clusters or running AfterPush EC2 instances; the `c7i-flex.large`
  worker is `terminated`.
- No AfterPush VPC, subnet, ENI, Internet Gateway, route-table candidate,
  NAT Gateway, Elastic IP, load balancer, or target group.
- No ECS clusters/services, RDS instances, DynamoDB tables, or Lambda
  resources named for AfterPush in the 17 enabled AWS regions checked.
- No AfterPush CloudWatch alarms/log groups, SNS topics, or Route 53 hosted
  zones in the target region. EKS-specific IAM roles/OIDC provider are gone;
  the GitHub Actions OIDC provider and `afterpush-github-actions-ecr` role
  remain for image delivery.
- Three ECR repositories and 12 image manifests remain:
  `afterpush-api`, `afterpush-platform-api`, and
  `afterpush-platform-worker`. Their reported image-size metadata sums to
  approximately 0.62 GiB; this is not a precise billable unique-layer total.
  The shared configuration defines `afterpush-runtime-worker`, but that
  repository was absent live and will be created by a future approved restore.
- The legacy `launchforge-api` ECS task-definition family has registered
  revisions but no ECS cluster/service. Task definitions alone do not run
  compute. Unrelated S3 buckets and other account resources were not changed.

The PostgreSQL StatefulSet was gracefully shut down, the volume was detached,
and encrypted snapshot **`snap-04c0bf420fd3f6715`** reached `completed` before
the original `vol-029214c0cf7f20222` was deleted. The snapshot is 5 GiB,
private to the account, sourced from that volume, and encrypted using the
enabled AWS-managed `aws/ebs` key. It remains available in `eu-central-1`;
the snapshot has not been restored and PostgreSQL recovery has not been
tested.

The Terraform backend bucket remains in `eu-central-1` with versioning enabled
and AES256 server-side encryption. The EKS state object has historical
versions and now represents an empty root; shared state still contains its
three managed resources. The three ECR repositories, OIDC delivery role, and
snapshot can incur ongoing storage charges. AWS Cost Explorer was available,
but its service-level data through 2026-10-19 was delayed and showed near-zero
unblended values/credits; it is not a zero-bill guarantee or resource-level
cost attribution.

The live EKS control plane was found to have drifted from Terraform: public
access was enabled with `0.0.0.0/0`, despite the committed private-only
configuration. Destroying the cluster removed the exposure. A future restore
must use private administrator access and verify the live endpoint and
security groups.

## CI, documentation, and repository hygiene

**Historical baseline PASS** — [GitHub Actions run #178](https://github.com/EthemKesim/AfterPush/actions/runs/39226946946)
for the previous Milestone 4 documentation commit `17bf79e` completed
successfully. It is not a check of this final shutdown/documentation change.
`Legacy Demo
Application Validate`, `Platform Validate`, and `Terraform Validate` all
passed. The Terraform job formatted, initialized and validated all three state
roots, then scanned Terraform configuration; the Platform job completed
database migration, tests, image scans, container checks and Helm rendering.

The prior review branch also passed [run #173](https://github.com/EthemKesim/AfterPush/actions/runs/39164255529).

Workflow source review confirms that CI is triggered only for pull requests to
`main` and pushes to `main`. The ECR image-delivery workflow is
`workflow_dispatch` only, requests `id-token: write` and `contents: read`, and
does not apply Terraform, publish GitOps changes, or activate the runtime
worker on an ordinary pull request. Actions are referenced by major-version
tags rather than full commit SHAs; that is a supply-chain hardening opportunity
to evaluate separately, not evidence that a live deployment ran.

**PASS for the final working tree:** a local checker found no broken relative
Markdown links across 30 Markdown files; `git diff --check` found no whitespace
errors; Trivy secret scanning found no findings; and both GitHub Actions YAML
files parsed successfully. No tracked `.env`, private-key, Terraform
state/plan, or credential-named file was found. Mermaid code fences and
node/edge structure were also reviewed statically; GitHub previously rendered
the README system diagram and both `docs/architecture.md` diagrams in the
review branch preview.

```bash
git diff --check
git ls-files | rg '(^|/)(\\.env($|\\.)|.*\\.(pem|key|p12|pfx|tfstate|tfplan)$)'
```

The README now explains the deployment-traceability problem up front, shows
that Argo CD renders Helm with Git-tracked values, includes reproduced local
demo evidence, and links to this report instead of freezing historical test
counts.

## Known limitations and release decision

Live EKS deployment, private API administrator access, Argo CD sync,
Kubernetes runtime verification, activation of the reconciliation CronJob,
remote GitOps publication, and production database migration were not
performed. They remain intentionally unverified.

The project is documented as a scoped `v1.0.0` portfolio prototype, not a
production platform. AWS-0164 remains a conditional source-design risk for
any future EKS restore and is not a production-readiness claim. Live shutdown
is verified; live EKS restore, Argo CD sync, and Kubernetes runtime health are
not. GitHub check, merge, tag, and release status are time-sensitive and are
reported separately from this dated validation evidence; verify the current
state on [PR #90](https://github.com/EthemKesim/AfterPush/pull/90).
