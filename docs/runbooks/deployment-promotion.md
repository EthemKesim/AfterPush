# Deployment promotion and timeline

AfterPush creates a new image version in `dev`.  A deployment is promoted only
after the runtime reconciliation worker has recorded both `status=published`
and `runtime_status=healthy` for that exact deployment.

## Flow

1. Create a `dev` deployment with its image tag.
2. The publication worker writes that deployment's immutable image, port and
   replica snapshot to GitOps. Argo CD and Kubernetes reconcile it.
3. The runtime worker observes Argo CD and Kubernetes. A fully synchronized,
   revision-matching rollout becomes `healthy`.
4. `POST /api/v1/deployments/{dev_id}/promote` with `staging` copies that
   source snapshot into a pending staging deployment.
5. Once staging is healthy, promotion to `prod` creates an
   `awaiting_approval` deployment. It has not reached the publication worker.
6. `POST /api/v1/deployments/{prod_id}/approve` rechecks the staging source,
   records `approved_at`, and changes the production deployment to `pending`.

The timeline endpoint is
`GET /api/v1/applications/{application_id}/deployment-timeline`. Each entry
contains `promotion_source_deployment_id`, so an interface can show exactly
which dev deployment became staging and which staging deployment became prod.

## Operational checks

- `awaiting_approval` must never appear in the publication worker's pending
  selection. It is deliberately not eligible until approval changes it to
  `pending`.
- A promotion copies `image_repository`, `image_tag`, `port`, and `replicas`
  from its source deployment. Changing the application's current defaults
  after dev has no effect on a promoted release.
- If a promotion returns HTTP 409, inspect the source deployment's `status`
  and `runtime_status`. It must be `published` and `healthy`.

## Production identity

This local API has no authenticated-user model yet, so it records approval
time but not an approver identity. In an EKS deployment this endpoint should
sit behind OIDC/IAM-backed API authentication and record the approved user's
identity in the audit trail. The readiness and immutable-snapshot rules are
enforced independently of that future authentication layer.
