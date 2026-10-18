# AfterPush

AfterPush is a single-operator platform engineering prototype for controlled
application deployments. It combines a FastAPI control plane, PostgreSQL-backed
deployment state, GitOps publication workers, Helm, Argo CD, Kubernetes,
Terraform, and GitHub Actions into a traceable deployment workflow.

The project focuses on the engineering work between “a deployment was
requested” and “the desired runtime state can be verified”: validating an
application definition, recording a revision, preparing its deployment
prerequisites, publishing versioned GitOps configuration, and reconciling the
result in Kubernetes.

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
        GitOps --> Argo[Argo CD]
        Argo --> Helm[Helm]
        Helm --> Cluster[Kubernetes / Amazon EKS]
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

The documented local demo, its related API/CLI/GitOps/migration checks, and
Helm lint/template validation most recently completed with **43 passing
tests**. The most recent broader platform suite recorded **811 passing tests**.
The [roadmap](docs/agent/roadmap.md) and [progress record](docs/agent/progress.md)
state the scope and evidence behind those results.

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

## Scope and current boundaries

AfterPush is a portfolio-grade, single-operator prototype—not a public,
multi-tenant SaaS or a fully managed production platform. The final release
does not claim that live AWS/EKS worker activation, Argo CD reconciliation, or
production database migration has been performed. Those operations require
reviewed image digests, secrets, configuration, scoped RBAC, and explicit
operator approval.

The `app/` directory remains a legacy TypeScript/Node.js demo application. It
is retained and independently validated in CI; the FastAPI platform under
`platform/` is the deployment system described in this README.
