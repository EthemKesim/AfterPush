# AfterPush Disaster Recovery Runbook

This runbook documents how to recover the local AfterPush Kubernetes platform
after a complete cluster loss.

The goal is to verify that the platform can be reconstructed from version-controlled
desired state instead of depending on manually configured Kubernetes resources.

---

## 1. Recovery Objectives

### Recovery Point Objective (RPO)

AfterPush is currently a stateless application.

Application source code, Terraform configuration, Helm charts, Argo CD
Applications, monitoring configuration, and platform configuration are stored
in Git.

For Git-managed platform configuration, the target is:

```text
RPO ≈ 0
```

This means recovery should restore the latest committed desired state.

This RPO does not currently cover a persistent application database because
AfterPush does not yet use one.

### Recovery Time Objective (RTO)

The RTO is measured during the disaster recovery experiment from the start of
recovery until the application and its critical monitoring path are healthy
again.

```text
Recovery start
      ↓
Cluster created
      ↓
Argo CD bootstrapped
      ↓
GitOps applications restored
      ↓
AfterPush Ready
      ↓
Blackbox probe_success = 1
      ↓
Recovery complete
```

The measured result is used as the local recovery baseline.

---

## 2. Disaster Scenario

The experiment assumes complete loss of the local Kubernetes cluster.

The following cluster-local resources are considered lost:

- Kubernetes Nodes and Pods.
- Deployments and ReplicaSets.
- Services and Ingress resources.
- HorizontalPodAutoscalers.
- ConfigMaps.
- Secrets.
- Argo CD.
- Prometheus.
- Grafana.
- Alertmanager.
- Blackbox Exporter.
- Metrics Server.
- NGINX Ingress Controller.

The Git repository and local Docker environment are assumed to remain
available.

This is a local disaster recovery experiment and should not be interpreted as
a complete AWS account or region disaster recovery test.

---

## 3. Recovery Sources

AfterPush uses different recovery sources for different types of state.

### Git Repository

Git contains the desired state for:

```text
Application source
Docker build definition
Helm chart
Argo CD Applications
Root Application
Ingress configuration
Monitoring configuration
Blackbox configuration
Metrics Server configuration
Kubernetes examples
Terraform infrastructure code
```

Git is therefore the primary source of truth for reconstructing the platform.

### Terraform Remote State

AWS Terraform state is stored separately in the configured remote S3 backend.

Terraform configuration describes the desired AWS infrastructure, while
Terraform state maps that configuration to real infrastructure resources.

The local Kubernetes DR experiment does not modify the AWS remote state.

### Container Image

The local kind environment uses:

```text
afterpush-api:metrics
```

with:

```text
imagePullPolicy: Never
```

Therefore the image must exist inside the newly created kind cluster before
the application can start.

This differs from a production environment, where the image would normally be
retrieved from a remote registry such as Amazon ECR.

### Kubernetes Secret

The application requires:

```text
afterpush-api-secret
```

in:

```text
afterpush-dev
```

The real Secret is intentionally excluded from Git.

The repository contains only:

```text
k8s/secret.example.yaml
```

Therefore Secret restoration is a manual prerequisite during this local
recovery experiment.

Production recovery should use an external secret-management system rather
than storing plaintext production secrets in Git.

---

## 4. Recovery Dependencies

The local recovery requires the following tools to remain available on the
operator machine:

```text
Docker
kind
kubectl
Git
Internet access for external Helm charts/manifests
```

The local AfterPush Docker image must also either still exist locally or be
rebuilt from the application source.

---

## 5. Bootstrap Problem

Argo CD manages the desired state of the platform, but Argo CD itself runs
inside the Kubernetes cluster.

Therefore a completely empty cluster cannot recover itself using Argo CD
until Argo CD has first been installed.

The recovery sequence is:

```text
Empty Kubernetes cluster
        ↓
Bootstrap Argo CD
        ↓
Restore required Secret
        ↓
Apply Root Application
        ↓
Argo CD discovers child Applications
        ↓
GitOps reconstructs platform
```

The tested Argo CD version for this environment is:

```text
v3.5.3
```

A fixed tested version should be preferred during recovery instead of
implicitly installing an unknown future version.

---

## 6. Recovery Procedure

### Step 1 — Create the kind Cluster

Recreate the cluster using the version-controlled kind configuration:

```bash
kind create cluster \
  --name afterpush \
  --config k8s/kind-config.yaml
```

Verify:

```bash
kubectl get nodes
```

Expected state:

```text
Ready
```

The kind configuration also restores the local port mappings required for the
Ingress path.

---

### Step 2 — Restore the Local Container Image

Verify that the application image still exists on the host:

```bash
docker image inspect afterpush-api:metrics
```

If the image no longer exists, rebuild it from source:

```bash
docker build -t afterpush-api:metrics ./app
```

Load the image into the kind cluster:

```bash
kind load docker-image afterpush-api:metrics --name afterpush
```

Verify that the image exists inside the kind node:

```bash
docker exec afterpush-control-plane \
  crictl images | grep afterpush
```

This step is required because the local Helm configuration uses:

```text
imagePullPolicy: Never
```

---

### Step 3 — Bootstrap Argo CD

Create the Argo CD namespace:

```bash
kubectl create namespace argocd
```

Install the tested Argo CD version:

```bash
kubectl apply --server-side -n argocd \
  -f https://raw.githubusercontent.com/argoproj/argo-cd/v3.5.3/manifests/install.yaml
```

Wait for Argo CD workloads:

```bash
kubectl wait --for=condition=Available \
  deployment/argocd-server \
  -n argocd \
  --timeout=300s
```

Verify:

```bash
kubectl get pods -n argocd
```

All core Argo CD components should eventually become `Running`.

---

### Step 4 — Restore the Application Secret

The real Secret is intentionally not stored in Git.

Create the application namespace if it does not already exist:

```bash
kubectl create namespace afterpush-dev
```

Restore the local Secret using the ignored local file:

```bash
kubectl apply -f k8s/secret.yaml
```

Do not commit `k8s/secret.yaml`.

Verify only the Secret's existence:

```bash
kubectl get secret afterpush-api-secret -n afterpush-dev
```

Do not print secret values during routine recovery verification.

---

### Step 5 — Bootstrap the Root Application

Apply the root Argo CD Application:

```bash
kubectl apply -f argocd/root-application.yaml
```

The root Application implements the App-of-Apps bootstrap pattern.

It watches:

```text
argocd/applications/
```

and causes Argo CD to create the platform Applications stored there.

---

### Step 6 — Wait for GitOps Reconciliation

Watch the Argo CD Applications:

```bash
kubectl get applications -n argocd -w
```

The expected Applications are:

```text
afterpush
afterpush-root
blackbox-exporter
ingress-nginx
metrics-server
monitoring
prometheus-crds
```

The target state is:

```text
SYNC STATUS:   Synced
HEALTH STATUS: Healthy
```

Some components may temporarily report `Progressing`, `Degraded`, `Missing`,
or another intermediate state while dependencies, CRDs, controllers, and
workloads are being created.

Temporary intermediate states should be allowed time to converge before
manual intervention is attempted.

---

### Step 7 — Verify the Application

Verify the AfterPush Pods:

```bash
kubectl get pods -n afterpush-dev
```

Verify the Deployment:

```bash
kubectl get deployment afterpush-api -n afterpush-dev
```

Expected state:

```text
READY:     2/2
AVAILABLE: 2
```

Verify the local HTTP path:

```bash
curl -i --max-time 5 \
  --resolve afterpush.local:80:127.0.0.1 \
  http://afterpush.local/health
```

Expected result:

```text
HTTP/1.1 200 OK
```

The application should also return:

```json
{"status":"healthy"}
```

---

### Step 8 — Verify Monitoring

Verify monitoring workloads:

```bash
kubectl get pods -n monitoring
```

Confirm that Prometheus, Grafana, Alertmanager, and Blackbox Exporter have
recovered.

The existence of Pods alone is not sufficient to declare recovery complete.

The monitoring signal must also be validated.

---

### Step 9 — Verify Outside-In Availability

Verify the Blackbox Probe:

```bash
kubectl get probe -n afterpush-dev
```

Temporarily expose Prometheus to the local machine:

```bash
kubectl port-forward -n monitoring \
  svc/monitoring-kube-prometheus-prometheus 9090:9090
```

In another terminal, query the Blackbox availability metric:

```bash
curl -sG 'http://localhost:9090/api/v1/query' \
  --data-urlencode 'query=probe_success{namespace="afterpush-dev",job="afterpush-blackbox"}'
```

The AfterPush Blackbox job should report:

```promql
probe_success{
  namespace="afterpush-dev",
  job="afterpush-blackbox"
}
```

with the value:

```text
1
```

This verifies that an independent observer can reach AfterPush through the
cluster's NGINX Ingress path.

In this local environment, the probe is cluster-internal. It does not validate
public DNS, Internet routing, a cloud load balancer, or public TLS.

---

## 7. Recovery Completion Criteria

The disaster recovery test is considered successful only when:

- Kubernetes node is `Ready`.
- Argo CD is operational.
- Root Application has restored the child Applications.
- Required Applications are `Synced` and `Healthy`.
- `afterpush-api` has its desired available replicas.
- The Ingress health request returns HTTP 200.
- Prometheus is operational.
- Grafana is operational.
- Alertmanager is operational.
- Blackbox Exporter is operational.
- `probe_success` for AfterPush equals `1`.

Only then should the recovery timer be stopped.

---

## 8. Recovery Architecture

```text
                  GitHub
                    │
                    │ desired state
                    ▼
             ┌──────────────┐
             │   Argo CD    │
             └──────┬───────┘
                    │
             App-of-Apps
                    │
       ┌────────────┼─────────────┐
       │            │             │
       ▼            ▼             ▼
   AfterPush      Ingress      Monitoring
       │                          │
       │                    ┌─────┼──────────┐
       │                    ▼     ▼          ▼
       │               Prometheus Grafana Alertmanager
       │                    │
       │                    │
       ▼                    │
 Kubernetes Service         │
       │                    │
       ▼                    │
 Application Pods           │
                            │
Blackbox Exporter ──────────┘
       │
       ▼
 NGINX Ingress
       │
       ▼
 AfterPush
```

---

## 9. Known Limitations

This recovery experiment intentionally has several limitations.

### Local Cluster

The experiment uses kind rather than a real multi-node cloud Kubernetes
cluster.

### Local Container Image

The application image is manually loaded into kind.

A production environment should restore images from a durable remote registry.

### Manual Secret Recovery

The application Secret is restored manually from a local ignored file.

A production platform should integrate with an external secret-management
system.

### Git Availability

This scenario assumes that the Git repository remains available.

Loss of both the Kubernetes environment and the source repository would
require a separate source-control backup strategy.

### Terraform State

The local Kubernetes recovery test does not simulate loss of the Terraform
remote-state backend.

A broader cloud DR strategy should protect infrastructure state independently.

### External Availability

The current Blackbox probe runs inside Kubernetes.

It validates the Ingress-to-application path but does not validate the full
public Internet, DNS, load-balancer, and TLS path.

---

## 10. Experiment Result

The complete cluster-loss recovery experiment was executed successfully.

### Timeline

```text
Recovery start:         2026-10-04 19:34:29
Recovery complete:      2026-10-04 19:49:49
Measured recovery time: 15 minutes 20 seconds
Result:                 PASSED
```

Recovery was considered complete only after the application and its
outside-in monitoring path were verified.

### Recovery Validation

The original kind cluster was completely deleted.

The following recovery sequence was then performed:

```text
Complete cluster loss
        ↓
New kind cluster
        ↓
Local application image restored
        ↓
Argo CD v3.5.3 bootstrapped
        ↓
Application Secret restored
        ↓
Root Application applied
        ↓
App-of-Apps reconciliation
        ↓
Platform components restored
        ↓
AfterPush restored
        ↓
Monitoring restored
        ↓
Outside-in availability verified
```

After GitOps reconciliation, all expected Argo CD Applications reached:

```text
SYNC STATUS:   Synced
HEALTH STATUS: Healthy
```

The recovered Applications were:

```text
afterpush
afterpush-root
blackbox-exporter
ingress-nginx
metrics-server
monitoring
prometheus-crds
```

The AfterPush Deployment recovered to:

```text
READY:     2/2
AVAILABLE: 2
```

The application health endpoint returned:

```text
HTTP/1.1 200 OK
```

with:

```json
{"status":"healthy"}
```

The Blackbox Probe was recreated successfully.

Prometheus reported:

```text
probe_success{
  namespace="afterpush-dev",
  job="afterpush-blackbox"
} = 1
```

This confirmed that the recovered application was reachable through the
cluster's NGINX Ingress path.

### Observed Recovery Behavior

During recovery, the `monitoring` Argo CD Application temporarily reported:

```text
Synced / Degraded
```

while `prometheus-crds` temporarily reported:

```text
Synced / Progressing
```

No manual intervention was required.

As the CRDs, controllers, and monitoring workloads became available, Argo CD
continued reconciling the desired state and both Applications automatically
converged to:

```text
Synced / Healthy
```

This demonstrated that temporary intermediate health states during bootstrap
do not necessarily represent recovery failure.

### Recovery Objective Result

For this local complete-cluster-loss experiment:

```text
Measured RTO = 15 minutes 20 seconds
```

For Git-managed platform configuration, no committed desired-state change was
lost during recovery.

Therefore the experiment was consistent with the platform's current target:

```text
RPO ≈ 0
```

for Git-managed configuration.

This RPO does not include persistent application data because AfterPush is
currently stateless.

### Result

**PASSED**

The experiment demonstrated:

- Complete Kubernetes cluster destruction and reconstruction.
- Recovery from version-controlled desired state.
- Successful Argo CD bootstrap.
- Successful App-of-Apps recovery.
- Automatic GitOps reconciliation.
- Application recovery to the desired replica count.
- Recovery of Ingress routing.
- Recovery of Prometheus, Grafana, Alertmanager, and Blackbox Exporter.
- Automatic convergence from temporary degraded monitoring states.
- HTTP health validation after recovery.
- Outside-in Blackbox validation after recovery.
- A measured local recovery time of 15 minutes 20 seconds.

### Lessons Learned

The experiment confirmed that most of the AfterPush platform can be
reconstructed rather than backed up as individual Kubernetes resources.

The primary recovery sources are:

```text
Git                 → platform desired state
Container image     → application runtime artifact
Secret source       → sensitive runtime configuration
Bootstrap procedure → initial GitOps recovery
```

The experiment also identified two local manual recovery dependencies:

```text
Local container image loading
Manual Kubernetes Secret restoration
```

These are acceptable for the current local laboratory environment but should
be removed from the production recovery path.

A production implementation should instead use:

```text
Remote container registry
        +
External secret-management system
        +
Automated infrastructure/bootstrap process
```

The current Blackbox validation is also cluster-internal and therefore proves
recovery of the Kubernetes Ingress path rather than complete public
Internet/DNS/TLS availability.