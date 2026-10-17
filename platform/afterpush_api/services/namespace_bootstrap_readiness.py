from uuid import UUID

import yaml
from kubernetes.utils.quantity import parse_quantity

from afterpush_api.services.namespace_bootstrap import (
    render_namespace_bootstrap,
)


def _quantity_matches(actual, expected) -> bool:
    """Compare Kubernetes resource quantities by numeric value."""
    if actual is None:
        return False

    try:
        return parse_quantity(str(actual)) == parse_quantity(str(expected))
    except (TypeError, ValueError, ArithmeticError):
        return False


class NamespaceBootstrapNotReady(RuntimeError):
    """Namespace bootstrap is missing or does not match expected policy."""


def verify_namespace_bootstrap(
    *,
    core_api,
    project_id: UUID,
    application_name: str,
    environment: str,
) -> str:
    expected = list(
        yaml.safe_load_all(
            render_namespace_bootstrap(
                project_id=project_id,
                application_name=application_name,
                environment=environment,
            )
        )
    )

    namespace = expected[0]["metadata"]["name"]

    try:
        actual_namespace = core_api.read_namespace(namespace)
        actual_quota = core_api.read_namespaced_resource_quota(
            "afterpush-resource-quota",
            namespace,
        )
        actual_limits = core_api.read_namespaced_limit_range(
            "afterpush-container-limits",
            namespace,
        )
    except Exception as exc:
        raise NamespaceBootstrapNotReady(
            f"Namespace bootstrap resources are unavailable: {namespace}"
        ) from exc

    labels = actual_namespace.metadata.labels or {}
    expected_labels = expected[0]["metadata"]["labels"]

    for key, value in expected_labels.items():
        if labels.get(key) != value:
            raise NamespaceBootstrapNotReady(
                f"Namespace security label mismatch: {key}"
            )

    quota = actual_quota.spec.hard or {}
    expected_quota = expected[1]["spec"]["hard"]

    for key, value in expected_quota.items():
        if not _quantity_matches(quota.get(key), value):
            raise NamespaceBootstrapNotReady(
                f"ResourceQuota mismatch: {key}"
            )

    actual_limit_items = actual_limits.spec.limits or []

    if len(actual_limit_items) != 1:
        raise NamespaceBootstrapNotReady(
            "Unexpected LimitRange configuration."
        )

    item = actual_limit_items[0]
    expected_item = expected[2]["spec"]["limits"][0]

    fields = {
        "default_request": "defaultRequest",
        "default": "default",
        "max": "max",
        "min": "min",
    }

    if item.type != expected_item["type"]:
        raise NamespaceBootstrapNotReady("LimitRange type mismatch.")

    for attribute, expected_key in fields.items():
        actual_values = getattr(item, attribute, None) or {}
        expected_values = expected_item[expected_key]

        for key, value in expected_values.items():
            if not _quantity_matches(actual_values.get(key), value):
                raise NamespaceBootstrapNotReady(
                    f"LimitRange mismatch: {expected_key}.{key}"
                )

    return namespace
