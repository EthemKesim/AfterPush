# Workload Pod Security Runbook

Each application Helm release creates a dedicated ServiceAccount with no
Kubernetes permissions and no mounted API token by default. The Deployment
explicitly uses that account.

The AfterPush API values also set `readOnlyRootFilesystem: true`. Its image
runs as UID 10001 and disables Python bytecode writes, so it does not need to
write into its image filesystem during normal operation.

For a third-party workload, enable a read-only root filesystem only after
testing it. If the process needs writable temporary storage, use a scoped
`emptyDir` mount for that path rather than making the image filesystem fully
writable.
