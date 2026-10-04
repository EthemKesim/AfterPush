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
```

One application Pod was then deleted:

```bash
kubectl delete pod <afterpush-pod> -n afterpush-dev
```

### Observed Behavior

Kubernetes immediately created a replacement Pod.

Because the only node was cordoned, the replacement Pod remained:

```text
Pending
```

The Deployment entered the following state:

```text
Desired replicas:   2
Available replicas: 1
```

The alert condition therefore became true:

```text
available replicas < desired replicas
1 < 2
```

After the condition remained true for more than one minute,
`AfterPushDeploymentDegraded` transitioned to `firing`.

Prometheus reported:

```text
alertname="AfterPushDeploymentDegraded"
alertstate="firing"
severity="warning"
```

Alertmanager also received the alert and reported it as active.

### Recovery

The node was made schedulable again:

```bash
kubectl uncordon afterpush-control-plane
```

Kubernetes scheduled the pending replacement Pod and restored the Deployment:

```text
READY:     2/2
AVAILABLE: 2
```

Prometheus then reported:

```text
available replicas = 2
desired replicas   = 2
```

Therefore:

```text
2 < 2 = false
```

The `AfterPushDeploymentDegraded` alert disappeared from the active `ALERTS`
series, confirming successful alert resolution.

### Result

**PASSED**

The experiment demonstrated:

- Kubernetes Deployment self-healing.
- Scheduler behavior when a node is cordoned.
- Detection of desired-vs-available replica degradation.
- Prometheus alert lifecycle.
- Prometheus-to-Alertmanager delivery.
- Automatic alert resolution after recovery.

### Monitoring Lesson

An alert based only on:

```promql
up{namespace="afterpush-dev", job="afterpush-api"} == 0
```

is not sufficient to detect every Pod failure.

A deleted Pod can disappear from Prometheus service discovery instead of
remaining as a known target with `up == 0`.

For this reason, AfterPush also monitors Kubernetes Deployment state using:

```promql
kube_deployment_status_replicas_available{
  namespace="afterpush-dev",
  deployment="afterpush-api"
}
<
kube_deployment_spec_replicas{
  namespace="afterpush-dev",
  deployment="afterpush-api"
}
```

This avoids hardcoding a replica count and remains compatible with
Horizontal Pod Autoscaling.

---

## Experiment 2 — Complete Application Unavailability

### Objective

Verify what happens when all AfterPush application Pods become unavailable
and determine whether application-level HTTP metrics can detect the resulting
user-visible outage.

### Steady State

Before injecting the failure:

- Kubernetes node was `Ready`.
- `afterpush-api` desired replicas: 2.
- `afterpush-api` available replicas: 2.
- Both application Pods were `Running` and `Ready`.
- `GET /version` returned HTTP `200 OK`.

### Hypothesis

If the only Kubernetes node is cordoned and all AfterPush application Pods
are deleted:

1. The Deployment will create replacement Pods.
2. The replacement Pods will remain `Pending`.
3. The application will have zero available replicas.
4. Requests through the Ingress will fail.
5. Application-level HTTP metrics will not record the failure if the request
   never reaches the application.

### Fault Injection

The node was made unschedulable:

```bash
kubectl cordon afterpush-control-plane
```

All AfterPush application Pods were deleted:

```bash
kubectl delete pod -n afterpush-dev -l app=afterpush-api
```

Kubernetes created two replacement Pods, but both remained:

```text
0/1   Pending
0/1   Pending
```

### User-Visible Failure

An external HTTP request was sent through the Ingress:

```bash
curl -i --max-time 5 \
  --resolve afterpush.local:80:127.0.0.1 \
  http://afterpush.local/version
```

The request returned:

```text
HTTP/1.1 503 Service Temporarily Unavailable
```

The response was generated by NGINX because there were no Ready application
Pods available behind the Kubernetes Service.

### Monitoring Blind Spot

The existing application metric was queried:

```promql
sum(
  rate(
    afterpush_http_requests_total{
      status_code=~"5..",
      route!="/health"
    }[5m]
  )
)
```

Prometheus returned no matching result.

The 503 response occurred before the request reached the Express application.
Therefore, the application's `prom-client` instrumentation could not observe
or count the failed request.

### Recovery

The node was made schedulable again:

```bash
kubectl uncordon afterpush-control-plane
```

Kubernetes automatically scheduled the pending Pods and restored the
Deployment:

```text
READY:     2/2
AVAILABLE: 2
```

The external request then returned:

```text
HTTP/1.1 200 OK
```

### Result

**PASSED**

The experiment demonstrated that application-level metrics alone cannot
guarantee end-to-end service availability.

### Monitoring Lesson

AfterPush provides inside-out monitoring using application metrics.

These metrics answer questions such as:

- How many requests reached the application?
- How long did those requests take?
- How many responses generated by the application were 5xx?

They cannot always answer:

> Can a user reach the service right now?

A failure in DNS, Ingress, Service routing, networking, or the application
backend can prevent a request from reaching the application entirely.

To close this observability gap, AfterPush now also uses Blackbox Exporter
to provide an outside-in availability signal:

```promql
probe_success{
  namespace="afterpush-dev",
  job="afterpush-blackbox"
}
```

This outside-in signal complements the existing application metrics rather
than replacing them.

The Blackbox probe used in the local Kubernetes environment runs inside the
cluster and sends an HTTP request through the NGINX Ingress Controller before
reaching the AfterPush Service and application Pods.

Therefore, it validates the Kubernetes ingress path, but it does not yet
validate a complete public Internet path such as public DNS, TLS termination,
or a cloud load balancer.

---

## Experiment 3 — Outside-In Failure Detection and Alert Lifecycle

### Objective

Verify that Blackbox monitoring detects complete AfterPush unavailability
through the Kubernetes ingress path and that the full alert lifecycle works
from failure detection to recovery.

The experiment validates the following monitoring pipeline:

```text
Blackbox Exporter
        ↓
probe_success
        ↓
Prometheus
        ↓
PrometheusRule
        ↓
Alertmanager
        ↓
Recovery / alert resolution
```

### Steady State

Before injecting the failure:

- Kubernetes node was `Ready`.
- `afterpush-api` had two available replicas.
- Both application Pods were `Running` and `Ready`.
- The NGINX Ingress route was reachable.
- Blackbox monitoring reported:

```text
probe_success = 1
```

- `AfterPushBlackboxProbeFailed` was inactive.

The Blackbox probe follows this path in the local environment:

```text
Blackbox Exporter
        ↓
NGINX Ingress Controller Service
        ↓
Ingress routing
        ↓
AfterPush Service
        ↓
AfterPush Pods
```

The probe sends the required HTTP `Host` header:

```text
Host: afterpush.local
```

so that NGINX can select the AfterPush Ingress rule.

### Hypothesis

If the only Kubernetes node is cordoned and all AfterPush application Pods
are deleted:

1. Kubernetes will create replacement Pods.
2. The replacement Pods will remain `Pending`.
3. No Ready application backend will remain.
4. The Blackbox HTTP probe through the Ingress will fail.
5. `probe_success` will transition from `1` to `0`.
6. `AfterPushBlackboxProbeFailed` will enter the `pending` state.
7. If the failure persists for one minute, the alert will transition to
   `firing`.
8. Alertmanager will receive the firing alert.
9. After the node is uncordoned, Kubernetes will restore the application.
10. `probe_success` will return to `1`.
11. Prometheus and Alertmanager will automatically resolve the alert.

### Fault Injection

The only Kubernetes node was marked unschedulable:

```bash
kubectl cordon afterpush-control-plane
```

All AfterPush application Pods were then deleted:

```bash
kubectl delete pod -n afterpush-dev -l app=afterpush-api
```

Kubernetes created replacement Pods, but they could not be scheduled:

```text
0/1   Pending
0/1   Pending
```

The existing Pods entered termination while the replacement Pods remained
pending.

### Outside-In Failure Detection

The Blackbox probe failed because the Ingress no longer had a healthy
AfterPush backend.

Prometheus reported:

```text
probe_success = 0
```

This is different from the application-level metrics used in Experiment 2.

The Blackbox signal is generated by an independent observer rather than by
the AfterPush application process itself.

Therefore, the failure can still be detected even when a request never
reaches Express.

### Alert Pending State

The following alert rule evaluates the Blackbox availability signal:

```promql
probe_success{
  namespace="afterpush-dev",
  job="afterpush-blackbox"
} == 0
```

The rule uses:

```text
for: 1m
```

After the probe began failing, Prometheus first reported:

```text
alertname="AfterPushBlackboxProbeFailed"
alertstate="pending"
severity="critical"
```

The `pending` state means that the alert condition is currently true, but it
has not yet remained true for the required one-minute duration.

This prevents very short transient failures from immediately becoming firing
alerts.

### Alert Firing State

The failure was intentionally kept active.

After the condition remained true for the configured duration, Prometheus
reported:

```text
alertname="AfterPushBlackboxProbeFailed"
alertstate="firing"
severity="critical"
```

This confirmed the transition:

```text
Inactive
   ↓
Pending
   ↓
Firing
```

### Alertmanager Delivery

Alertmanager was queried after Prometheus transitioned the alert to
`firing`.

Alertmanager reported:

```text
alertname="AfterPushBlackboxProbeFailed"
state="active"
severity="critical"
```

This verified that the alert successfully travelled from Prometheus to
Alertmanager.

The local environment currently uses a null receiver for this alerting
pipeline, so the experiment verifies alert generation and Alertmanager
delivery without sending a real Slack, email, PagerDuty, or other external
notification.

### Recovery

The Kubernetes node was made schedulable again:

```bash
kubectl uncordon afterpush-control-plane
```

Kubernetes automatically scheduled the replacement application Pods.

The Deployment returned to its healthy state:

```text
READY:     2/2
AVAILABLE: 2
```

After the application became reachable again, Blackbox monitoring reported:

```text
probe_success = 1
```

### Alert Resolution

Immediately after service recovery, the Blackbox availability metric had
already returned to:

```text
probe_success = 1
```

while the alert briefly remained in the `firing` state until the next
Prometheus rule evaluation.

After the following evaluation cycle, Prometheus returned no active
`AfterPushBlackboxProbeFailed` alert:

```json
{
  "status": "success",
  "data": {
    "resultType": "vector",
    "result": []
  }
}
```

Alertmanager also no longer returned
`AfterPushBlackboxProbeFailed` in its active alerts.

The complete lifecycle was therefore:

```text
probe_success = 1
        ↓
No alert
        ↓
Failure injected
        ↓
probe_success = 0
        ↓
Pending
        ↓
Firing
        ↓
Alertmanager Active
        ↓
Recovery
        ↓
probe_success = 1
        ↓
Prometheus Resolved
        ↓
Alertmanager Resolved
```

### Grafana Validation

The Blackbox availability signal is also visualized in the
`AfterPush Observability` Grafana dashboard.

The dashboard contains the following panel:

```text
Outside-In Availability
```

The panel maps:

```text
probe_success = 1 → UP
probe_success = 0 → DOWN
```

and uses different visual states to make current service availability
immediately visible.

After recovery, the dashboard displayed:

```text
Outside-In Availability: UP
```

confirming that the GitOps-managed dashboard was reading the recovered
Blackbox signal correctly.

### Result

**PASSED**

The experiment successfully demonstrated:

- Controlled complete application failure.
- Outside-in HTTP availability monitoring.
- Detection of failures that application instrumentation cannot observe.
- Blackbox `probe_success` transition from `1` to `0`.
- Prometheus alert transition from inactive to pending.
- Prometheus alert transition from pending to firing.
- Successful Prometheus-to-Alertmanager delivery.
- Kubernetes recovery after the node became schedulable.
- Blackbox `probe_success` transition from `0` back to `1`.
- Automatic Prometheus alert resolution.
- Automatic Alertmanager resolution.
- Grafana visualization of the recovered availability state.

### Resilience Lesson

No single monitoring signal is sufficient on its own.

AfterPush now observes failures from multiple perspectives:

```text
Application metrics
    → What is happening inside the application?

Kubernetes state metrics
    → Can Kubernetes maintain the desired application state?

Blackbox monitoring
    → Can an independent observer reach the application through Ingress?
```

Together, these signals provide stronger failure detection than any one of
them individually.

The local Blackbox probe should not be interpreted as a full Internet-level
synthetic availability test.

It currently verifies:

```text
Blackbox Exporter
        ↓
NGINX Ingress
        ↓
Kubernetes Service
        ↓
AfterPush Pods
```

It does not currently verify:

```text
Public DNS
    ↓
Internet routing
    ↓
Public cloud load balancer
    ↓
TLS/HTTPS
    ↓
Kubernetes Ingress
```

When AfterPush is validated on its final cloud environment, an external probe
can extend the same monitoring model to the complete public request path.