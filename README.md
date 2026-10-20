# AfterPush

AfterPush addresses a common deployment gap: accepting configuration does not
by itself show which exact revision was requested, what was published, or
whether the desired state was later verified. It is a single-operator platform
engineering prototype that combines a FastAPI control plane, PostgreSQL-backed
deployment state, GitOps publication workers, Helm, Argo CD, Kubernetes,
Terraform, and GitHub Actions into a traceable deployment workflow.

The project validates an application definition, records an immutable
deployment revision, prepares its prerequisites, publishes versioned GitOps
configuration, and keeps runtime verification separate from that publication.

## What it demonstrates

- A FastAPI platform API for configuration validation, Helm-values rendering,
  projects, applications, deployments, promotion, health, and metrics.
- PostgreSQL and Alembic migrations for durable deployment revisions,
  publication claims, Git commit references, and runtime status.
- Worker-driven deployment prerequisites, namespace and RBAC gates, GitOps
  publication, retry/recovery paths, and runtime reconciliation.
- Helm charts, Argo CD definitions, Kubernetes security resources, and
  Terraform-managed AWS/EKS infrastructure with separate state boundaries.
- Reproducible local proof of the core path without writing to GitHub, AWS,
  Argo CD, or a Kubernetes cluster.

## System architecture

```mermaid
flowchart LR
    Operator[Single operator] --> API[FastAPI platform API]

    subgraph Control plane
        API <--> DB[(PostgreSQL)]
        API --> Workers[Prerequisite and publication workers]
    end

    subgraph GitOps publication
        Workers --> GitOps[GitOps repository\nversioned Helm values]
    end

    subgraph Desired-state delivery
        Chart[Helm chart]
        GitOps --> Argo[Argo CD]
        Chart --> Argo
        Argo -->|renders Helm with Git-tracked values\nand reconciles| Cluster[Kubernetes / Amazon EKS]
    end

    Terraform[Terraform] -. provisions .-> Cluster
    CI[GitHub Actions CI] -. validates .-> API
    CD[Manual GitHub Actions CD] -. publishes images .-> ECR[Amazon ECR]
    ECR --> Cluster
```

The control plane records intent and deployment state. Publication workers
write the desired deployment configuration to GitOps; they do not write
directly to Argo CD. Argo CD and Helm then reconcile that versioned desired
state in Kubernetes.

## Deployment engineering highlights

- **Revision traceability:** each deployment carries its revision, source
  deployment relationship, publication claim, published Git commit SHA, and
  runtime verification state.
- **Safe publication gates:** namespace readiness and application-scoped RBAC
  are checked before a deployment is claimed and published. Work that cannot be
  safely proven ready is deferred rather than marked successful.
- **GitOps separation:** runtime intent is committed as Helm values in Git;
  Argo CD remains the reconciler of desired state.
- **Recovery-aware workers:** publication attempts use claims, retry timing,
  completion checks, and recovery-oriented paths to avoid treating a partial
  operation as complete.
- **Infrastructure boundaries:** Terraform separates shared resources from the
  EKS lifecycle, and CI validates all tracked Terraform roots without applying
  infrastructure.
- **Least-privilege direction:** Kubernetes/Argo RBAC resources are scoped to
  platform tasks, the API ingress defaults to internal access, and the image
  delivery workflow uses AWS OIDC rather than stored long-lived AWS keys.

## Reproducible local demo

The local demo exercises the platform without a cloud account or a running
cluster. It uses only the local `afterpush_test` PostgreSQL database and a
temporary GitOps working directory.

First follow the [local PostgreSQL setup](docs/demo/local-postgres.md), then
run this command from the repository root:

```bash
DATABASE_URL=postgresql+psycopg://afterpush:afterpush_local_dev@127.0.0.1:5432/afterpush_test \
TEST_DATABASE_URL=postgresql+psycopg://afterpush:afterpush_local_dev@127.0.0.1:5432/afterpush_test \
platform/.venv/bin/python -m pytest platform/tests/demo/test_local_demo_journey.py -q
```

The test validates and renders `platform/examples/afterpush.yaml`, creates a
project, application, and development deployment through FastAPI, produces
temporary GitOps values, and checks the staging-promotion rule. The
[complete demo guide](docs/demo/local-journey.md) also links to the isolated
publication-worker test, which commits to a temporary bare Git repository.

This is intentionally not a live AWS/EKS deployment demonstration: it does
not push to a remote Git repository, sync Argo CD, roll out Kubernetes
workloads, or claim live runtime health.

A short, reproduced local example looks like this:

```text
$ afterpush validate platform/examples/afterpush.yaml
✓ AfterPush configuration is valid.

$ afterpush deploy platform/examples/afterpush.yaml --gitops-root <temporary-directory>
✓ GitOps deployment prepared: <temporary-directory>/afterpush-api/values.yaml
```

The generated file contains the rendered image, service, ingress, and resource
values. The [local demo](docs/demo/local-journey.md) and its isolated
publication-worker test additionally prove deployment/promotion policy and a
commit to a temporary bare Git repository.

## Technology choices

- **FastAPI and PostgreSQL:** express the platform API and persist deployment
  lifecycle state with a relational, migration-managed model.
- **Python workers:** keep prerequisite checks, GitOps publication, recovery,
  and reconciliation logic testable outside an active cluster.
- **Helm, Argo CD, and Kubernetes:** keep deployment configuration declarative
  and reconcile Git-tracked desired state.
- **Terraform:** make networking, EKS, ECR, IAM/OIDC, and supporting AWS
  resources reviewable infrastructure as code.
- **GitHub Actions:** validates pull requests and `main`; image delivery is a
  separate, manually dispatched AWS OIDC workflow.

## Validation

Pull requests and pushes to `main` run three CI jobs:

- `Legacy Demo Application Validate` runs tests, linting, dependency audit,
  container build, image scan, and a health check for the legacy demo app.
- `Platform Validate` prepares `afterpush_test`, runs Alembic migrations,
  executes platform tests, and builds the platform API image.
- `Terraform Validate` checks formatting and validates the root, shared, and
  EKS Terraform configurations without a backend or an apply.

Validation evidence is dated and scoped in the
[final validation report](docs/final-validation.md), rather than treated as a
permanent test-count claim. That report distinguishes local, CI, static, and
live-environment evidence and links each outcome to a reproducible command.

## Cost-safe AWS operations

For the optional AWS prototype environment, a state-backed operator tool
provides safe previews before any cloud action:

```bash
./scripts/aws-env.sh status
./scripts/aws-env.sh start --dry-run
./scripts/aws-env.sh stop --dry-run
./scripts/aws-env.sh verify
```

It retains shared ECR/OIDC recovery assets, limits normal teardown to the EKS
Terraform state root, and requires an explicit account/region check,
confirmation, data-recovery acknowledgement, and reviewed Terraform plan for
any live action. The [cost-safe AWS operations runbook](docs/runbooks/aws-cost-safe-operations.md)
explains live read-only inventory, restore boundaries, residual costs, and why
the tool never promises a zero AWS bill.

## Verified AWS shutdown

The original live AfterPush EKS environment was shut down on 2026-10-19. A
short-lived EKS/Argo CD screenshot demo was later deployed, verified
`Healthy`/`Synced`, and shut down on 2026-10-20 from a fresh 23-resource
Terraform destroy plan. The EKS cluster, worker/root disk, demo internal ALB
and target group, demo VPC/networking, and EKS-scoped IAM resources are absent.
The final demo evidence and post-teardown AWS inventory are recorded in the
[temporary EKS evidence](docs/agent/temporary-eks-demo-evidence.md).

The PostgreSQL StatefulSet was gracefully stopped and its detached 5 GiB EBS
volume was snapshotted as encrypted recovery asset
`snap-04c0bf420fd3f6715`; only after completion was the original volume
deleted. A later request referenced `snap-026638e6765e0067c`, which was not
found in `eu-central-1`; the verified `snap-04...` recovery point remains
completed and encrypted. The snapshot, retained ECR image storage, versioned
Terraform state, and a tiny orphaned CloudWatch flow-log group may still incur
storage charges. Cost Explorer showed account-level usage offset by credits;
this is not proof of a zero bill. A live restore and snapshot-based database
recovery have **not** been performed. See the [final validation report](docs/final-validation.md)
and [recovery runbook](docs/runbooks/aws-cost-safe-operations.md) before restoring.

## Further documentation

- [Technical architecture](docs/architecture.md)
- [Portfolio and interview guide](docs/portfolio.md)
- [Local demo journey](docs/demo/local-journey.md)
- [Terminal demo recording script](docs/demo/terminal-demo.md)
- [Local PostgreSQL setup](docs/demo/local-postgres.md)
- [Deployment publication runbook](docs/runbooks/deployment-publication.md)
- [Publication recovery runbook](docs/runbooks/deployment-publication-recovery.md)
- [Deployment promotion runbook](docs/runbooks/deployment-promotion.md)
- [Runtime reconciliation runbook](docs/runbooks/runtime-reconciliation.md)
- [Platform API metrics runbook](docs/runbooks/platform-api-metrics.md)
- [Network policy validation runbook](docs/runbooks/network-policy-validation.md)
- [Cost-safe AWS operations](docs/runbooks/aws-cost-safe-operations.md)
- [v1.0.0 release notes](docs/releases/v1.0.0.md)

## Scope and current boundaries

AfterPush is a portfolio-grade, single-operator prototype—not a public,
multi-tenant SaaS or a fully managed production platform. The final release
was followed by a temporary EKS demo whose Argo CD reconciliation and
application health were verified before shutdown. This is not a production
readiness or live restore claim. Runtime-reconciliation worker activation,
snapshot-based database recovery, and production migration remain unverified.
Future live operations require reviewed image digests, secrets, configuration,
scoped RBAC, and explicit operator approval.

The `app/` directory remains a legacy TypeScript/Node.js demo application. It
is retained and independently validated in CI; the FastAPI platform under
`platform/` is the deployment system described in this README.
