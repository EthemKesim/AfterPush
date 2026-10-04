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

AfterPush currently provides inside-out monitoring using application metrics.

These metrics answer questions such as:

- How many requests reached the application?
- How long did those requests take?
- How many responses generated by the application were 5xx?

They cannot always answer:

> Can a real user reach the service right now?

A failure in DNS, Ingress, Service routing, networking, or the application
backend can prevent a request from reaching the application entirely.

AfterPush therefore needs an outside-in availability signal.

The next step is to add black-box monitoring that probes the service through
its real HTTP path and exposes an availability metric such as:

```promql
probe_success
```

This will complement the existing application metrics rather than replace
them.
