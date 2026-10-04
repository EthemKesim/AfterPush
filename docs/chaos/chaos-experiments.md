# AfterPush Chaos & Resilience Experiments

This document records controlled failure experiments performed against the
AfterPush Kubernetes environment.

The goal is to verify that the platform can detect failures, maintain service
where possible, recover automatically, and correctly resolve alerts after
recovery.

---

## Experiment 1 — Pod Failure with Scheduling Disabled

### Objective

Verify Kubernetes self-healing behavior and confirm that the monitoring stack
detects a Deployment that cannot maintain its desired number of available
replicas.

### Steady State

Before injecting the failure:

- Kubernetes node was `Ready`.
- `afterpush-api` desired replicas: 2.
- `afterpush-api` available replicas: 2.
- Both application Pods were `Running` and `Ready`.
- `AfterPushDeploymentDegraded` was inactive.

### Hypothesis

If one application Pod is deleted while the only Kubernetes node is cordoned:

1. The Deployment will create a replacement Pod.
2. The replacement Pod will remain `Pending` because no schedulable node exists.
3. One existing application replica will remain available.
4. Available replicas will become lower than desired replicas.
5. `AfterPushDeploymentDegraded` will fire after the condition persists for one minute.
6. After the node is uncordoned, Kubernetes will schedule the replacement Pod and restore the Deployment to its desired state.
7. The alert will automatically resolve.

### Fault Injection

The node was marked unschedulable:

```bash
kubectl cordon afterpush-control-plane