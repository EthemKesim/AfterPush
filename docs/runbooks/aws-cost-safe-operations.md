# Cost-safe AWS operations

This runbook describes the single-operator AWS lifecycle interface for the
AfterPush portfolio prototype. It is deliberately state-backed and
conservative: it does not perform broad name-based cleanup, does not expose
credentials, and does not claim that an AWS bill is zero.

Use it only from the repository root:

```bash
./scripts/aws-env.sh status
./scripts/aws-env.sh start --dry-run
./scripts/aws-env.sh stop --dry-run
./scripts/aws-env.sh verify
```

The commands above are local previews. They inspect committed source only; no
AWS API, remote Terraform state, Kubernetes cluster, or database is contacted.

## Safety model

`--live` enables **read-only** AWS inventory for `status` and `verify`.
`--execute` enables a Terraform operation only after all of these gates pass:

- the requested account ID and the configured `eu-central-1` region match;
- the expected Terraform backend/state is accessible;
- resource ownership is proved by that state, not by a similar name;
- the operator supplies the exact `--confirm START` or `--confirm STOP` word;
- EKS stop acknowledges data/secrets recovery with
  `--data-recovery-confirmed`.

The tool creates an ephemeral Terraform plan, applies exactly that plan only
when explicitly executed, and removes the temporary plan afterward. A failed
operation leaves Terraform state in place and tells the operator to run
`status`/`verify` before retrying. Repeated stop against an accessible but empty
state is a successful no-op.

Never run a broad AWS cleanup command. Candidate resources returned by a live
inventory still require an ownership review before manual action.

## Resource inventory and lifecycle policy

| Resource group | Source/lifecycle | Decision | Cost or recovery reason |
| --- | --- | --- | --- |
| EKS cluster, managed node group, EKS VPC/subnets/routes, EBS CSI addon and EKS/IRSA roles | `terraform/eks/` | Destroy when the EKS demo is stopped | EKS control plane and nodes are recurring costs; state-backed configuration can recreate them. |
| ECR `afterpush-api` and configured `afterpush-runtime-worker`; GitHub Actions OIDC role | `terraform/shared/` | Retain | The API repo and OIDC role are in state; the worker repo is configured with `prevent_destroy` but was absent from the live account and will be created during restore. |
| ECR `afterpush-platform-api` and `afterpush-platform-worker` | Manually created in `eu-central-1` | Retain for recovery | Existing images are not Terraform-managed; preserve until the placeholder-image deployment path is rebuilt and tested. |
| Terraform S3 state bucket and its S3 lockfiles | Terraform backend | Retain | Required to prove ownership and restore state; never destroyed by this tool. |
| Legacy ECS, ALB, VPC endpoints, logs, alarms, SNS/KMS and `launchforge-api` ECR | `terraform/` | Manual review | Separate legacy root; its ECR uses `force_delete`, so it is never an automatic stop target. |
| Controller-created load balancers/target groups, EBS volumes, public IPv4/EIPs, Route 53 and manually created resources | AWS outside a known state | Manual review | They may be billable but cannot safely be assumed to belong exclusively to AfterPush. |
| DynamoDB | No configured backend table | Manual review | The configured Terraform backends use S3 lockfiles, not DynamoDB. |

The `verify --live` inventory asks AWS about EKS, EC2/EBS, ECS, NAT gateways,
EIPs, load balancers/target groups, account-wide ECR repositories, the state
bucket, CloudWatch logs/alarms, SNS, KMS, and Route 53. It labels the result as
a candidate or manual-review item; it never deletes anything and cannot prove
a zero bill. Inventory output is a count, not proof that every listed resource
belongs to AfterPush; review ownership before any manual action.

## Status and verification

For a source-only report:

```bash
./scripts/aws-env.sh status
./scripts/aws-env.sh verify
```

For a read-only account inventory, provide the account explicitly. Do not put
credentials on the command line; use a reviewed AWS profile, SSO session, or
other normal AWS credential provider.

```bash
./scripts/aws-env.sh status --live --account-id <12-digit-account-id> --profile <profile>
./scripts/aws-env.sh verify --live --account-id <12-digit-account-id> --profile <profile>
```

`status` reports the configured lifecycle and static inventory. `verify`
adds the remaining-cost checklist. Neither command changes AWS state.

## Start and restore

The default restore order is `shared` then `eks`: retain/reconcile image
delivery assets first, then recreate drifted or intentionally destroyed EKS
resources from the existing backend state. The legacy primary root is excluded
by default because it is not required for the EKS platform path.

First preview the operation:

```bash
./scripts/aws-env.sh start --dry-run
```

An approved live restore is intentionally verbose:

```bash
./scripts/aws-env.sh start \
  --execute --confirm START \
  --account-id <12-digit-account-id> --profile <profile> \
  --targets shared,eks
```

The command runs `terraform init`, proves the expected state is readable,
creates a detailed plan per root, and applies only that plan. A missing or
unreadable backend is a refusal, not a cue to create another state. An empty
but readable state represents a deliberate stopped/initial lifecycle and can
be recreated from committed configuration.

Terraform does not install Argo CD in this repository. After EKS has been
restored, obtain private control-plane access and continue with the reviewed
[disaster recovery runbook](../disaster-recovery/recovery-runbook.md): restore
required secrets out of band, bootstrap Argo CD, apply the root Application,
and observe synchronization. The tool validates that those GitOps sources
exist, but it does not claim a cluster rollout or application health. The
runtime-reconciliation CronJob remains suspended until its image, Secret,
ConfigMap, and RBAC are reviewed.

### Restore PostgreSQL from the retained snapshot

The snapshot is not automatically substituted for a dynamically provisioned
PVC. After EKS and the EBS CSI driver are ready, create a new encrypted volume
from the snapshot in the original Availability Zone:

```bash
aws ec2 create-volume \
  --snapshot-id snap-04c0bf420fd3f6715 \
  --availability-zone eu-central-1a \
  --volume-type gp3 \
  --encrypted \
  --profile <profile> \
  --region eu-central-1
```

Record the returned volume ID. Create a static CSI PersistentVolume for that
volume and a matching `afterpush-system` PVC named
`postgres-data-afterpush-postgres-0` before starting the PostgreSQL StatefulSet.
The current PostgreSQL image is major version 17. Restore the database Secret
out of band, start PostgreSQL, and verify database recovery before starting
the API Deployments. The filesystem and database were not tested by a live
restore; inspect them during restoration rather than assuming success.

## Stop

Preview first:

```bash
./scripts/aws-env.sh stop --dry-run --targets eks
```

Before a live EKS teardown, back up any persistent application data that is in
scope, preserve required secrets outside Git, and review the Terraform state.
The repository has no Terraform-managed PostgreSQL/RDS resource; its database
and secret recovery are therefore an explicit operator responsibility. Once
that review is complete, the destructive command is:

```bash
./scripts/aws-env.sh stop \
  --execute --confirm STOP --data-recovery-confirmed \
  --account-id <12-digit-account-id> --profile <profile> \
  --targets eks
```

This command destroys only the `terraform/eks/` state root. It retains shared
ECR/OIDC assets and refuses to destroy the state backend. After it completes,
run a read-only verification and manually inspect controller-created resources:

```bash
./scripts/aws-env.sh verify --live --account-id <12-digit-account-id> --profile <profile>
```

The legacy primary root needs a separate review. It can be planned only with
`--allow-legacy-root`; an actual stop also needs
`--legacy-ecr-backup-confirmed` because its `launchforge-api` repository has
`force_delete = true`. This is intentionally outside the normal EKS stop path.

## Verified final shutdown (2026-10-19)

The live account and `eu-central-1` region were verified before any destroy.
The EKS root contained 23 managed resources, and the fresh destroy plan matched
the previously reviewed scope: `0 add, 0 change, 23 destroy`. Terraform removed
the EKS cluster, managed node group/worker, EKS VPC/networking, and EKS-scoped
IAM resources. The first apply removed the cluster resources but could not
detach the Internet Gateway while EKS-managed ENIs still had mapped public
addresses. CloudTrail, the remaining state, and a fresh two-resource plan were
reviewed; after the ENIs were gone, the same lifecycle tooling completed the
VPC/IGW cleanup. The EKS state is now empty.

The running EKS cluster had drifted from source configuration: its control
plane allowed public access from `0.0.0.0/0`, although the committed Terraform
configuration defaults to private-only. Destroying the cluster removed that
exposure. A future restore must use private administrator access and recheck
the live endpoint and managed security groups.

No Kubernetes Ingress, ALB/NLB, target group, NAT Gateway, or Elastic IP
existed at shutdown, so there was no ingress-created load balancer to delete.
The one `c7i-flex.large` node terminated. Legacy ECS had no clusters/services;
registered `launchforge-api` task-definition revisions remain but do not
provide running capacity. The account also had no matching RDS, DynamoDB, or
Lambda resources in the 17 enabled regions checked.

PostgreSQL shutdown and recovery:

- `afterpush-api` and `afterpush-platform-api` Deployments and the
  `afterpush-postgres` StatefulSet were scaled to zero and their pods were
  gone.
- The PVC mapped to `vol-029214c0cf7f20222` (5 GiB, `gp3`, encrypted) was
  detached. A completed snapshot was created after graceful PostgreSQL
  shutdown: **`snap-04c0bf420fd3f6715`**. Its source volume, 5 GiB size,
  `completed` state, AWS account ownership, encryption, `aws/ebs` key, and
  private share permissions were verified.
- The original volume was deleted only after that verification. The snapshot
  remains; restoring it into a new volume and recovering PostgreSQL has not
  been tested. For a future recovery, create a new encrypted gp3 volume from the
  snapshot in `eu-central-1a`, install/restore the EBS CSI driver, and manually
  bind a static CSI PV/PVC to the StatefulSet claim
  `postgres-data-afterpush-postgres-0` before starting PostgreSQL 17. Recreate
  the database Secret out of band, verify the filesystem/database recovery, and
  only then start the API deployments. This repository does not automate that
  snapshot-to-PV procedure.

The versioned Terraform S3 backend remains in `eu-central-1`, with AES256
server-side encryption and historical state versions. The EKS key
`afterpush/eks-validation/terraform.tfstate` is now an accessible empty state;
the shared state still contains its three resources. Shared GitHub Actions
OIDC remains. `afterpush-api`, `afterpush-platform-api`, and
`afterpush-platform-worker` ECR repositories remain with 12 image manifests
whose reported image-size sum is about 0.62 GB. The shared Terraform
configuration also defines `afterpush-runtime-worker`; it was absent live and
will be created by the approved shared-root restore plan. The platform ECR
repositories are outside Terraform state and should be retained until their
manual image-placeholder deployment path is reviewed.

Remaining possible charges are snapshot storage for the 5 GiB recovery
snapshot, ECR storage, and the versioned S3 state/lock objects. IAM/OIDC
resources do not run compute. No EKS, running EC2 node, EBS volume, load
balancer, target group, NAT Gateway, or Elastic IP remained in the direct
post-shutdown service checks. Cost Explorer returned only delayed,
service-level unblended data through 2026-10-19 and is not evidence of a
zero-dollar bill. Other unrelated account resources and buckets were left
untouched.

### Retained-resource cost and recovery matrix

| Resource identifier | Retention reason | Possible ongoing charge | Deletable later? | Restore impact |
| --- | --- | --- | --- | --- |
| `snap-04c0bf420fd3f6715` | Only verified PostgreSQL recovery point | EBS snapshot storage per retained GB-month; actual incremental usage may be below 5 GiB | Yes, after the database is restored and the recovery point is no longer needed | Deleting it removes the preserved PostgreSQL recovery source |
| `afterpush-api`, `afterpush-platform-api`, `afterpush-platform-worker` ECR repositories | Keep images that existed before shutdown; preserve the manually configured platform image path | ECR image-layer storage and any data transfer; image-size metadata totals about 0.62 GiB before layer deduplication | Yes, after confirming the needed images can be rebuilt and published | Deletion requires a rebuild/push before workloads that reference those images can start |
| `afterpush-terraform-state-833090513321` S3 bucket and versioned state keys | Recovery-critical state and state history | S3 storage for current/prior versions and lockfiles, plus API requests | The bucket must not be deleted; old versions may be reviewed/pruned only with a separate state-retention decision | Removing current state can prevent safe ownership checks; removing all versions eliminates rollback/recovery history |
| `afterpush-github-actions-ecr` role and `token.actions.githubusercontent.com` provider | OIDC-based image publishing identity | No running-compute charge; IAM/OIDC itself has no recurring resource charge | Yes, but only with a replacement delivery identity planned | Removing it disables the current GitHub Actions ECR publishing trust |
| `alias/aws/ebs` AWS-managed KMS key | EBS snapshot encryption | No customer-managed key monthly fee; KMS API usage may be chargeable | AWS manages this key; do not attempt to disable it | Required by the retained encrypted snapshot |

The registered `launchforge-api` ECS task-definition revisions remain but do
not run tasks or incur compute charges by themselves. They can be deregistered
later if desired; the Terraform ECS task definition can be registered again
from source. No inference about unrelated account buckets or resources is made
by this table.

## Failure recovery and limitations

- If `terraform plan` or `apply` fails, do not retry blindly. Run `status` and
  `verify --live`, inspect the current state and a fresh plan, then retry only
  with the same explicit approval. Terraform may have completed part of a
  destroy before failing; the state can accurately contain only the remaining
  resources.
- An inaccessible state, an account/region mismatch, or an unexpected state
  address is a safety refusal. Fix the ownership/state issue rather than
  bypassing the gate.
- Public-node-subnet AWS-0164 remains accepted only for the narrow temporary
  single-operator portfolio scope recorded in the final validation report.
- Live Terraform, Kubernetes, Argo CD, and billing behavior are not exercised
  by repository tests. A successful local test proves command safety logic,
  not an end-to-end cloud restore.
