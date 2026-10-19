# Primary Terraform security profile

This root defines the legacy ECS example and supporting AWS resources. It is
separate from `shared/` (longer-lived ECR and GitHub OIDC resources) and
`eks/` (the EKS lifecycle); each root has its own Terraform state boundary.

## Legacy ECS ALB

The ALB defaults to `internal` and accepts HTTPS only. Applying this root
requires `acm_certificate_arn`; Terraform does not invent a certificate or
create a plaintext listener. Local Node/Docker demo commands do not use this
ALB and remain certificate-free.

Public exposure is an explicit operator decision. Set `alb_access_mode` to
`public`, provide a valid ACM certificate ARN, and provide a non-empty,
narrow `public_alb_ingress_cidrs` allowlist. A public mode without an
allowlist fails the ALB precondition. Do not use `0.0.0.0/0` as a substitute
for an administrator or consumer network boundary.

## Alert encryption

The alerts SNS topic uses a customer-managed, rotation-enabled KMS key. Its
key policy keeps account-root administration while granting only the SNS topic
and the named CloudWatch target-5xx alarm the KMS actions needed to publish
encrypted notifications. Enabling this key changes the infrastructure plan;
review it before any apply.

Validation and CI use `terraform init -backend=false` and `terraform validate`.
They never apply this configuration or contact the configured backend.
