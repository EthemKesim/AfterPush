# Deployment Publication Recovery Runbook

Use this runbook when a deployment remains in `publishing` beyond the
configured claim timeout.

## 1. Decide whether GitOps publication succeeded

Run the GitOps recovery worker first. It compares the immutable deployment
snapshot with the GitOps repository. If they match, it records the published
commit without creating another Git commit.

```bash
python -m afterpush_api.workers.gitops_recovery --timeout-minutes 15
```

If the result is `recovered`, stop here.

## 2. Reset only an unpublished, abandoned claim

Do not reset a claim solely because it is old. First establish that the
worker holding the claim cannot still push to the GitOps repository. For a
Kubernetes Job, inspect the Job and its Pod, confirm it has terminated, and
prevent it from being restarted before proceeding.

Use the deployment ID and the current claim ID from the deployment record:

```bash
python -m afterpush_api.workers.gitops_claim_reset \
  --deployment-id DEPLOYMENT_UUID \
  --claim-id CLAIM_UUID \
  --timeout-minutes 15 \
  --confirm-worker-stopped
```

The command uses a conditional database update. It resets the claim only if
the deployment is still `publishing`, still has the supplied claim ID, and
has been claimed for at least the timeout period.

Expected results:

- `reset`: the deployment returned to `pending`; the publication worker may
  process it again.
- `not_stale`: the claim is still recent; investigate rather than reset it.
- `claim_changed`: another recovery action changed the deployment; reload its
  current state before taking action.
- `not_found`: the deployment ID is incorrect or has been removed.

## Why the confirmation matters

A timeout shows that no completion was recorded, not that the original worker
has stopped. Two workers publishing different revisions at the same time can
briefly make GitOps describe an older revision. Explicit confirmation keeps
the reset safe while Git publication remains an external side effect outside
the PostgreSQL transaction.
