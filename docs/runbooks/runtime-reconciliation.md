# Runtime reconciliation worker

The runtime worker answers a different question from the GitOps publication
worker. Publication confirms that a deployment revision was committed to the
GitOps repository. Runtime reconciliation checks whether Argo CD synced that
exact commit and whether the Kubernetes Deployment completed its rollout.

```text
Deployment row -> GitOps commit -> Argo CD sync -> Deployment rollout
                                          ^              |
                                          |--------------|
                                       runtime worker
```

The worker records one of these values on the deployment: `healthy`,
`progressing`, `degraded`, `out_of_sync`, `revision_mismatch`, or
`unverified`. An `unverified` result means AfterPush could not safely prove the
state; it must not be interpreted as a successful deployment.

## Safe activation order

The CronJob is committed with `spec.suspend: true`. Applying the manifest does
not start it. Before enabling it in a non-production environment, prepare:

1. A worker image referenced by an immutable digest in
   `REPLACE_RUNTIME_WORKER_IMAGE`. The CD workflow publishes it to the
   `afterpush-runtime-worker` ECR repository after that repository is created
   by `terraform/shared`.
2. The existing `afterpush-api-db` Secret with a `DATABASE_URL` key.
3. `afterpush-runtime-worker-config` from
   `k8s/runtime-reconciliation/config.example.yaml`, using the GitOps
   repository URL that Argo CD is configured to use.
4. The ServiceAccount and the per-application Argo CD and Deployment reader
   Roles generated through GitOps.

Then render and review the manifests, replace the image placeholder, and only
then change `spec.suspend` to `false` through the approved GitOps change.

Creating the ECR repository and extending the GitHub OIDC policy requires a
reviewed Terraform plan and an explicit infrastructure approval. No worker is
started merely by creating the repository.

## Permissions

The ServiceAccount needs an API token because it reads cluster state. It has no
cluster-wide read role. Each application receives two narrow Roles: `get` for
its own Argo CD Application in the `argocd` namespace and `get` for its own
Deployment in its project namespace. The worker cannot list, modify, or delete
workloads.

## Troubleshooting

If a deployment becomes `unverified`, inspect the worker Job logs first. A
Kubernetes `403` normally indicates missing per-application RBAC; a `404` can
mean Argo CD has not created the expected resource yet; an API timeout is
recorded as `observer_error` without copying infrastructure details into the
database. `revision_mismatch` means the observed Pod template annotation does
not match the immutable deployment revision saved by AfterPush.
