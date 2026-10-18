# Terminal demo script

This script records a 60–90 second terminal walkthrough of AfterPush without
AWS, EKS, Argo CD, or a remote Git repository. It demonstrates the platform's
control-plane and GitOps-publication contracts using only `afterpush_test` and
temporary local directories.

## Before recording

Follow the [local PostgreSQL setup](local-postgres.md). Confirm that the
connection points to `afterpush_test`, then prepare this local-only variable
before starting screen capture:

```bash
export DEMO_DATABASE_URL='postgresql+psycopg://afterpush:afterpush_local_dev@127.0.0.1:5432/afterpush_test'
```

The value is the fixed local test credential documented in the demo setup; it
is not a production credential. Do not show credentials, cloud-console tabs,
or unrelated terminal history in the recording.

## Recording order

### 1. Validate an application definition — 0:00–0:10

```bash
platform/.venv/bin/afterpush validate platform/examples/afterpush.yaml
```

Show the successful validation result. Explain: “AfterPush first validates a
small application definition before it becomes deployment configuration.”

### 2. Render the desired Helm values — 0:10–0:25

```bash
platform/.venv/bin/afterpush render platform/examples/afterpush.yaml | sed -n '1,28p'
```

Point out the application name, image tag, service port, and replicas. Explain:
“The definition becomes declarative Helm values; it is not yet a cluster
deployment.”

### 3. Prepare temporary GitOps values — 0:25–0:40

```bash
DEMO_GITOPS_ROOT=$(mktemp -d)
platform/.venv/bin/afterpush deploy platform/examples/afterpush.yaml --gitops-root "$DEMO_GITOPS_ROOT"
sed -n '1,28p' "$DEMO_GITOPS_ROOT/afterpush-api/values.yaml"
```

Show that the generated values are written only below the temporary directory.
Explain: “This is the desired state that a publication flow can commit to
GitOps. This command does not push to GitHub or contact Argo CD.”

### 4. Prove the control-plane lifecycle — 0:40–0:55

```bash
DATABASE_URL="$DEMO_DATABASE_URL" TEST_DATABASE_URL="$DEMO_DATABASE_URL" \
platform/.venv/bin/python -m pytest platform/tests/demo/test_local_demo_journey.py -q
```

Before recording, set `DEMO_DATABASE_URL` to the local `afterpush_test`
connection string described in the local demo guide. Explain while the test
runs: “This contract creates the project, application, and development
revision through FastAPI, then checks the staging-promotion policy. Healthy
runtime is simulated here only to demonstrate that policy.”

### 5. Prove an isolated GitOps publication — 0:55–1:15

```bash
DATABASE_URL="$DEMO_DATABASE_URL" TEST_DATABASE_URL="$DEMO_DATABASE_URL" \
platform/.venv/bin/python -m pytest \
  platform/tests/deployments/test_deployment_publication_worker_integration.py -q
rg -n 'publish_claimed_deployment|published_sha|rev-parse|values_path' \
  platform/tests/deployments/test_deployment_publication_worker_integration.py
```

Explain: “The publication worker uses a temporary bare Git repository. The
test verifies the commit SHA stored in PostgreSQL, re-clones the repository,
and checks the exact generated `values.yaml`, including its revision, image,
port, and replica count.”

### 6. Close with the boundary — 1:15–1:25

Show [the architecture diagram](../architecture.md) or the terminal prompt and
say: “A real deployment continues when Argo CD observes Git and renders Helm
for Kubernetes. This local demo deliberately stops before remote Git, Argo CD,
and EKS.”

## What the recording proves

The walkthrough tells a technical story rather than showing only a pytest
summary:

1. Config becomes renderable desired state.
2. The API lifecycle creates a revision and tests promotion rules.
3. The publication worker creates and verifies a real local Git commit.
4. Argo CD/EKS are clearly identified as the next, intentionally unexecuted
   delivery stage.

The temporary Git repository is removed by the integration test. The separate
temporary values directory can be inspected after recording and is never a
remote GitOps source.

## README placement

Do not add a placeholder image or an unrecorded video to the README. Once a
reviewed terminal recording exists, place its short GIF or video link directly
below the opening paragraph of the **Reproducible local demo** section in the
[README](../../README.md). Add one sentence stating that it uses
`afterpush_test` and temporary Git state only.
