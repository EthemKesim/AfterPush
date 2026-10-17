from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest
from starlette.responses import Response


HTTP_REQUESTS = Counter(
    "afterpush_http_requests_total",
    "Total HTTP requests handled by the AfterPush Platform API.",
    labelnames=("method", "route", "status_code"),
)

HTTP_REQUEST_DURATION_SECONDS = Histogram(
    "afterpush_http_request_duration_seconds",
    "Duration of HTTP requests handled by the AfterPush Platform API.",
    labelnames=("method", "route", "status_code"),
)


def metrics_response() -> Response:
    """Return Prometheus's text exposition format."""
    return Response(
        content=generate_latest(),
        media_type=CONTENT_TYPE_LATEST,
    )
