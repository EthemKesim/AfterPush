# Final validation and release-readiness review

**Review date:** 2026-10-20
**Repository baseline:** `main` at `dc5b434` (merged PR #90)
**Review branch:** `chore/finalize-eks-demo-teardown`

This report records the final review evidence for the portfolio prototype. A
result marked PASS proves only the stated local, CI, or static scope; it does
not prove a live AWS/EKS deployment.

## Outcome summary

| Area | Outcome | Evidence type |
| --- | --- | --- |
| FastAPI platform tests | PASS | 835 passed, 1 deprecation warning against local `afterpush_test` |
| Legacy Node application | PASS | Local test, lint, build, dependency audit |
| Container builds and image scans | PASS | Local Docker and Trivy |
| Helm, GitOps, and Argo CD source checks | PASS | Offline lint, render, and static inspection |
| Terraform format and configuration validation | PASS | All three roots initialized backend-disabled and validated |
| Terraform security configuration | PASS — scoped acceptance | Static Trivy scan plus documented single-operator risk acceptance |
| AWS lifecycle safety tool | PASS — local/mock and live shutdown | Preview/guard tests plus state-backed EKS teardown; live restore not verified |
| GitHub Actions for the prior review branch | PASS | GitHub Actions run #173 |
| GitHub Actions before final repository changes | PASS — historical | Earlier PR #90 head `758fd1d` had all three checks pass; this is not validation of the current teardown PR |
| Live AWS shutdown | PASS | EKS state empty; cluster, worker, VPC, and original PostgreSQL volume removed |
| Temporary EKS screenshot demo | PASS — deployed, healthy, then shut down | Argo CD `Synced`/`Healthy`, API `2/2`, HPA `3%/50%`, ALB targets healthy; no restore claim |
| Live EKS/PostgreSQL restore and post-restore reconciliation | NOT VERIFIED | Temporary demo sync/health was verified before teardown; no restore or post-restore check was performed |

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

After the inventory regression test was added, the CI-equivalent full-suite
command was rerun after applying migrations to the local test database:

```bash
cd platform
python -m alembic upgrade head
cd ..
python -m pytest platform/tests -q
```

Result: **835 passed, 1 warning**. This current result supersedes the earlier
grouped run count above.

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
| `afterpush-api:ci` | `/health` returned healthy | `node` | 0 |
| `afterpush-platform-api:ci` | `/health` and `/metrics` succeeded | `10001` | 0 |
| `afterpush-runtime-worker:ci` | reconciliation worker `--help` succeeded | `10001` | 0 |

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

On the final PR working tree, recursive formatting passed and each root
initialized with `-backend=false` and validated. The CI-configured Trivy scan
was run against a clean source copy that excluded ignored local state, provider
caches, and historical plan snapshots. It exited successfully with
`exit-code: 0` and reported the same one AWS-0039 HIGH scanner limitation and
two AWS-0164 HIGH public-subnet findings documented below; it reported no
CRITICAL findings. The workflow's non-blocking scan policy does not mean every
finding was removed.

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

## Original live shutdown and cost audit (2026-10-19)

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
- No AfterPush CloudWatch alarms, SNS topics, or Route 53 hosted zones in the
  target region. The later account-wide log-group query found one existing
  `/vpc/afterpush/flow-logs` group; the earlier `/aws`-prefix query had missed
  it. EKS-specific IAM roles/OIDC provider are gone;
  the GitHub Actions OIDC provider and `afterpush-github-actions-ecr` role
  remain for image delivery.
- At the original shutdown, three ECR repositories and 12 image manifests
  remained:
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

## Temporary EKS demo and final re-teardown (2026-10-20)

The temporary `afterpush-eks` environment was brought up only to complete the
single-operator screenshot demonstration. The workload reached Argo CD
`Synced`/`Healthy` for both the API and metrics-server Applications; the API
Deployment was `2/2` ready, HPA CPU was `3%/50%`, the metrics API was
available, and both internal ALB targets were healthy. The health endpoint
returned the expected `afterpush-platform-api` response. These results are
deployment evidence only, not production-readiness or restore evidence.

Before Terraform cleanup, the Kubernetes Ingress was deleted so its controller
removed the cluster-tagged internal ALB and target group. The fresh EKS destroy
plan contained exactly 23 deletes and no add/change actions. The repository's
guarded lifecycle command completed the destroy. Read-only checks then found
no EKS cluster, running EC2 worker, worker root EBS volume, ALB, target group,
demo VPC/subnets/Internet Gateway, NAT Gateway, or allocated EIP in
`eu-central-1`. The EKS Terraform state is empty; shared state retains three
resources. The source configuration was returned to private-only EKS API
access and `main` GitOps revisions.

The specifically requested snapshot `snap-026638e6765e0067c` was not found in
`eu-central-1`. The prior verified PostgreSQL snapshot
`snap-04c0bf420fd3f6715` remains `completed`, encrypted, 5 GiB, and owned by
account `833090513321`; its source volume has been deleted and a restore has
not been tested.

Post-teardown inventory identified the following remaining known AfterPush
storage exposures:

- Three ECR repositories hold 15 manifests with 777,307,835 bytes of reported
  image size (about 0.724 GiB before layer deduplication).
- The versioned, AES256 S3 state bucket has 164 object versions totaling
  2,635,331 bytes; the current EKS state object is an accessible 476-byte
  empty state.
- CloudWatch log group `/vpc/afterpush/flow-logs` contains 1,311 bytes, has no
  tags and no retention policy. Terraform source expects 30-day retention, but
  no active VPC Flow Log producer exists. The group is kept for manual
  audit-retention review because it is outside the EKS state root.
- The AWS-managed `alias/aws/ebs` key is enabled for the snapshot; IAM/OIDC
  resources do not run compute.

Cost Explorer's available account-level period 2026-10-01 through
2026-10-19 showed `$46.8076168713` Usage and `-$46.8076169982` Credits. This
is delayed data, includes unrelated services, and is not attributable to the
retained items. Credits explain the near-zero/negative display; they do not
prove a zero bill. A rough retained-storage estimate is `$0.25–$0.33/month`,
primarily snapshot and ECR storage, with S3 history and the current log group
below a cent. It excludes transfers, requests, future log ingestion, taxes,
and unrelated account resources; it is not an invoice.

The lifecycle inventory was tightened after the audit exposed a false
negative: `verify --live` now includes account-owned EBS snapshots and
account-wide CloudWatch log groups, and its output correctly states that AWS
APIs were queried without resources being changed.

Local checks on this branch: Platform suite **835 passed, 1 existing
deprecation warning**.
The legacy app `npm ci`, tests (**3 passed**), lint, TypeScript build,
HIGH/CRITICAL Trivy image scan, container health test, and npm audit passed
after a semver-compatible lockfile update resolved a pre-existing HIGH Vite
advisory. The local runtime was Node 26.8.1, while GitHub Actions specifies
Node 22. CLI validation/rendering, API and worker image builds, container
health/metrics, worker help, Helm lint, and Helm rendering passed. These are
local results; the current PR's GitHub Actions checks must be reported from
GitHub and are not inferred from this validation.

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

The temporary EKS deployment, Argo CD synchronization, workload health, and
internal ALB targets were verified before teardown. A private API restore,
live EKS recreation, PostgreSQL snapshot restore, activation of the
reconciliation CronJob, and production database migration were not performed.
They remain intentionally unverified.

The project is documented as a scoped `v1.0.0` portfolio prototype, not a
production platform. AWS-0164 remains a conditional source-design risk for
any future EKS restore and is not a production-readiness claim. The temporary
demo was shut down after its live health verification; EKS restore and
PostgreSQL recovery remain untested. GitHub check, merge, tag, and release
status are time-sensitive and are reported separately from this dated
validation evidence; verify the current PR checks before merging.
