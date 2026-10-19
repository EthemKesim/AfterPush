# AfterPush portfolio guide

Use this guide for conversations, a CV, LinkedIn, and GitHub metadata. It is
deliberately based on the implementation and local evidence in this repository:
AfterPush is a single-operator platform engineering prototype, not a public
multi-tenant SaaS or evidence of a completed live EKS deployment.

## 30-second project pitch

AfterPush is a single-operator platform engineering prototype for making
application deployments traceable and controlled. A FastAPI control plane and
PostgreSQL record versioned deployment intent, while workers prepare namespace
and RBAC prerequisites and publish approved GitOps values. Argo CD renders the
Helm chart and reconciles the desired state in Kubernetes; a separate runtime
worker is designed to verify the expected Git revision and rollout. I built it
to explore safe GitOps publication, promotion, recovery, and testing without
presenting a local demo as a live production deployment.

## 2–3-minute technical walkthrough

I built AfterPush to explore a practical platform engineering problem: a
deployment request is not the same as a successfully running workload. The
project keeps the path between those two states explicit and auditable.

The control plane is a FastAPI API backed by PostgreSQL and Alembic. It manages
projects, applications, and deployments. A new deployment starts in `dev` with
a monotonically increasing revision and a copied snapshot of the image, port,
and replica count. That snapshot matters because promotion should reproduce a
known deployment rather than pick up mutable application defaults. A published
and runtime-healthy `dev` deployment can be promoted to staging; production
promotion has an additional explicit approval step.

I separated publication from runtime verification. Prerequisite workers prepare
the namespace and application-scoped GitOps RBAC first. If Kubernetes readiness
cannot be proven, the work waits instead of being marked successful. The
publication worker then claims one pending deployment, rechecks those gates,
and writes approved values through an isolated Git checkout. It records the
Git commit SHA only when the same claim still owns completion. Argo CD—not the
publication worker—observes the Git-tracked desired state, renders the Helm
chart with the configured values, and applies the resulting resources to
Kubernetes.

That split is important for failure handling. Publication claims prevent two
workers from treating the same deployment as theirs. If a claim becomes stale,
recovery verifies whether GitOps already contains the exact requested values
before completing the database state; it does not blindly create another push.
Runtime reconciliation is a separate observer that compares the expected Git
commit and revision with Argo CD and Kubernetes rollout state. Uncertainty is
stored as an unverified or error result, not as success.

For infrastructure, Terraform separates primary, shared, and EKS
configuration roots. CI validates all three without applying infrastructure.
The manually dispatched image-delivery workflow uses GitHub OIDC to publish
images to ECR, rather than storing long-lived AWS keys. The EKS API ingress
defaults to internal access, and the runtime worker remains suspended until its
image, secrets, configuration, and narrow RBAC are reviewed.

I validate the core story locally with `afterpush_test`, temporary schemas and
directories, and a temporary bare Git repository. The demo proves config
validation, values rendering, deployment revision/promotion policy, and a
GitOps commit contract. It intentionally does not claim remote Git, Argo CD,
or live EKS rollout verification. That boundary is part of the design, not a
hidden limitation.

## CV project description

**AfterPush — Platform Engineering and GitOps Deployment Prototype**

- Built a FastAPI and PostgreSQL control plane with Alembic migrations for
  versioned application deployments, immutable promotion snapshots,
  publication claims, Git commit traceability, and runtime status.
- Implemented worker-based namespace/RBAC prerequisites, isolated GitOps
  publication, stale-claim recovery, and separate Kubernetes/Argo CD runtime
  reconciliation to keep desired-state publication distinct from verification.
- Defined Helm, Argo CD, Kubernetes security resources, Terraform state
  boundaries, and GitHub Actions validation; demonstrated the core lifecycle
  through local PostgreSQL and temporary Git repository integration tests.
- Completed a state-verified teardown of the live EKS demo, retained its
  versioned Terraform backend and delivery identity, and preserved PostgreSQL
  in an encrypted EBS snapshot; the restore path remains untested live.

## LinkedIn project description

AfterPush is a single-operator platform engineering prototype that models a
controlled deployment lifecycle rather than only building infrastructure. Its
FastAPI and PostgreSQL control plane records versioned deployments and
promotions, while worker processes gate namespace/RBAC readiness and publish
GitOps values through isolated Git checkouts. Argo CD and Helm reconcile the
Git-tracked desired state in Kubernetes, and a separate runtime observer is
designed to verify the expected commit and rollout. The project uses Terraform,
AWS OIDC, Helm, Argo CD, Kubernetes, and GitHub Actions, with local tests that
prove the core lifecycle without claiming a live AWS/EKS deployment.

## GitHub About and topics

**About**

> Cloud-native deployment platform prototype featuring GitOps automation, Kubernetes, AWS, Terraform, Helm, Argo CD, and CI/CD.

**Topics**

`platform-engineering`, `devops`, `gitops`, `kubernetes`, `aws`, `terraform`,
`argocd`, `helm`, `deployment-automation`, `ci-cd`, `fastapi`, `python`

These are recommendations only. Applying GitHub metadata is a separate,
user-approved repository change.

## Evidence boundary

Prefer “validated locally” or “demonstrated with temporary Git integration
tests” when discussing this project. Do not say that the runtime worker,
Argo CD synchronization, or a restored EKS rollout has been operated
successfully in a live environment. The live EKS shutdown and encrypted
PostgreSQL snapshot are verified; the snapshot has not been restored. For
commands and proof, see the [local demo](demo/local-journey.md), [terminal
recording script](demo/terminal-demo.md), and [technical
architecture](architecture.md).
