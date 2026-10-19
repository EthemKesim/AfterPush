# Final validation and release-readiness review

**Review date:** 2026-10-19
**Repository baseline:** `main` at `69e2fd0` (merged PR #88)
**Review branch:** `codex/final-security-remediation`

This report records the final review evidence for the portfolio prototype. A
result marked PASS proves only the stated local, CI, or static scope; it does
not prove a live AWS/EKS deployment.

## Outcome summary

| Area | Outcome | Evidence type |
| --- | --- | --- |
| FastAPI platform tests | PASS | Local `afterpush_test` PostgreSQL |
| Legacy Node application | PASS | Local test, lint, build, dependency audit |
| Container builds and image scans | PASS | Local Docker and Trivy |
| Helm, GitOps, and Argo CD source checks | PASS | Offline lint, render, and static inspection |
| Terraform format and configuration validation | PASS | Backend-disabled temporary copies |
| Terraform security configuration | BLOCKED | Static Trivy scan; one topology decision remains |
| GitHub Actions for the prior review branch | PASS | GitHub Actions run #173 |
| GitHub Actions for this remediation branch | PASS | CI run #176: all three required jobs succeeded |
| Live AWS/EKS, Argo CD, and runtime reconciliation | NOT VERIFIED | Intentionally not contacted |

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

Result: **820 passed, 1 warning**. The environment's per-command time limit
required two complete directory groups (492 and 328 tests), both against the
same `afterpush_test` database. This suite covers Alembic
migration paths, deployment revisions and promotion, prerequisite/namespace/
RBAC gates, publication/recovery/stale-claim paths, runtime reconciliation,
GitOps integration, CLI validation/rendering, local demo, and infrastructure
and workflow contract tests.

Warning: Starlette's `TestClient` reports that its current `httpx` integration
is deprecated. It did not fail a test; dependency compatibility should be
reviewed when the test stack is upgraded.

### Legacy demo application

**PASS** — from `app/`:

```bash
npm test && npm run lint && npm run build && npm audit --audit-level=high
```

Result: **3 passed**; lint and TypeScript build succeeded; `npm audit` found
**0 vulnerabilities** at the HIGH/CRITICAL threshold. An initial sandboxed
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
runtime-worker observation. No cluster was contacted.

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

**BLOCKED — no CRITICAL finding remains, but one operator topology decision is
still required before a live-release claim.** Trivy 0.74.0 was run on an
isolated copy of Terraform source. The copy excluded local provider caches,
untracked state/backup files, and untracked `tfplan*` artifacts; none were
modified or committed. This avoids treating an old plan snapshot as current
source configuration.

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
| AWS-0164 (two subnets) | CONDITIONAL RISK / BLOCKER | The managed node group still uses public subnets with automatic public IPv4 for bootstrap and image pulls. Disabling it safely requires an approved private-node route through NAT or VPC endpoints and changes recurring cost/connectivity. No such architecture was invented. |
| AWS-0054 | RESOLVED | The legacy ECS ALB has only an HTTPS listener using an operator-supplied ACM certificate; plaintext HTTP was removed. |
| AWS-0053 | RESOLVED | The legacy ECS ALB defaults to `internal`. Public mode requires an explicit selection and non-empty CIDR allowlist. |
| AWS-0136 | RESOLVED | The alerts topic now uses a rotation-enabled customer-managed KMS key. The key policy permits only account-root administration, the named SNS topic, and the named CloudWatch alarm's required KMS actions. |

The clean-source scan reported exactly one AWS-0039 HIGH finding and two
AWS-0164 HIGH findings; it reported **no CRITICAL findings**. The first is the
documented scanner limitation above. The second is a real design trade-off and
is not an automatically accepted risk. Focused infrastructure tests protect
the private endpoint, modern-encryption assumption, explicit public-node
trade-off, TLS-only/internal ALB default, public allowlist guard, SNS KMS key,
and existing Terraform/CI state-boundary contracts.

## CI, documentation, and repository hygiene

**PASS** — [GitHub Actions run #176](https://github.com/EthemKesim/AfterPush/actions/runs/39223293007)
for remediation commit `65275f7` completed successfully. `Legacy Demo
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

**PASS locally:** Markdown links were checked for repository-relative targets;
`git diff --check` found no whitespace errors; no tracked `.env`, private key,
Terraform state/plan, or credential file was found. Mermaid code fences and
node/edge structure were reviewed statically, then GitHub rendered the README
system diagram and both `docs/architecture.md` diagrams successfully in the
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

**Release readiness: BLOCKED for a reviewed `v1.0.0` release today.** The
project is a well-tested, documented portfolio prototype, and its former
critical Terraform defaults have been remediated. Before a live-infrastructure
claim or Milestone 4 closure, the operator must either accept the documented
public-node-subnet risk or approve a costed private-node/NAT-or-endpoint
topology. This review does not create a tag, GitHub Release, or
production-readiness claim.
