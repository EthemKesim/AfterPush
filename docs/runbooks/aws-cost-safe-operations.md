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
| ECR `afterpush-api` and `afterpush-runtime-worker`; GitHub Actions OIDC role | `terraform/shared/` | Retain | Images and delivery identity enable restore. Both repositories use `prevent_destroy`. |
| Terraform S3 state bucket and its S3 lockfiles | Terraform backend | Retain | Required to prove ownership and restore state; never destroyed by this tool. |
| Legacy ECS, ALB, VPC endpoints, logs, alarms, SNS/KMS and `launchforge-api` ECR | `terraform/` | Manual review | Separate legacy root; its ECR uses `force_delete`, so it is never an automatic stop target. |
| Controller-created load balancers/target groups, EBS volumes, public IPv4/EIPs, Route 53 and manually created resources | AWS outside a known state | Manual review | They may be billable but cannot safely be assumed to belong exclusively to AfterPush. |
| DynamoDB | No configured backend table | Manual review | The configured Terraform backends use S3 lockfiles, not DynamoDB. |

The `verify --live` inventory asks AWS about EKS, EC2/EBS, ECS, NAT gateways,
EIPs, load balancers/target groups, ECR, CloudWatch logs/alarms, SNS, KMS, and
Route 53. It labels the result as a candidate or manual-review item; it never
deletes anything and cannot prove a zero bill.

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

## Failure recovery and limitations

- If `terraform plan` or `apply` fails, do not retry blindly. Run `status` and
  `verify --live`, inspect the state and failed plan, then retry only with the
  same explicit approval.
- An inaccessible state, an account/region mismatch, or an unexpected state
  address is a safety refusal. Fix the ownership/state issue rather than
  bypassing the gate.
- Public-node-subnet AWS-0164 remains accepted only for the narrow temporary
  single-operator portfolio scope recorded in the final validation report.
- Live Terraform, Kubernetes, Argo CD, and billing behavior are not exercised
  by repository tests. A successful local test proves command safety logic,
  not an end-to-end cloud restore.
