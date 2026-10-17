# Platform API metrics

The FastAPI platform API exposes Prometheus metrics at `/metrics`. Helm's
ServiceMonitor scrapes this endpoint every 15 seconds and assigns a stable
`application` label. Prometheus rules then use the same metric names for the
5xx-rate, latency, and SLO alerts.

The two application metrics are:

- `afterpush_http_requests_total{method,route,status_code}`
- `afterpush_http_request_duration_seconds{method,route,status_code}`

`route` uses FastAPI route templates such as
`/api/v1/deployments/{deployment_id}` rather than individual IDs. This prevents
unbounded metric cardinality: a high-cardinality label creates a new Prometheus
time series for every value and can make monitoring expensive or unstable.

The `/metrics` endpoint itself is not counted. A scrape is monitoring traffic,
not a user request, and counting it would make the system's request-rate and
latency panels reflect Prometheus frequency instead of product traffic.

If the `AfterPushTargetDown` alert fires, first confirm that the ServiceMonitor
can reach `/metrics`, then inspect `up` and the platform API logs. If an HTTP
alert fires, filter the request counter by route and status code before looking
at traces or logs for that API route.
