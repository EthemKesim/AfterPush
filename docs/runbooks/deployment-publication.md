# Deployment Publication Runbook

The publication worker changes the GitOps repository.  It does not contact
Argo CD directly; Argo CD later observes the Git commit and reconciles it to
Kubernetes.

## Before running

Confirm the target repository and database environment.  `--execute` is
required so an accidental local command cannot publish a deployment.

```bash
export AFTERPUSH_GITOPS_REPOSITORY_URL=https://github.com/ORG/GITOPS_REPO.git
python -m afterpush_api.workers.gitops_publication --limit 20 --execute
```

Do not run this command against a live database or GitOps repository without
the approved operational change.  In a scheduled Kubernetes Job, the command
and its image tag should be reviewed as part of the manifest change.

## Reading the result

- `published`: a deployment snapshot was committed to GitOps and its commit
  SHA was stored in PostgreSQL.
- `deferred`: namespace or RBAC prerequisites are not ready.  No deployment
  claim or Git commit was created; `publication_checked_at` records the
  attempt so untried deployments receive priority in later batches.
- `skipped`: the deployment was no longer eligible, usually because another
  worker or a newer revision already changed it.
- `errors`: investigate the worker log.  A failed publication after its claim
  is handled through the publication recovery runbook.
