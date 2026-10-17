from copy import deepcopy
from types import SimpleNamespace
from uuid import UUID

import pytest
import yaml

from afterpush_api.services.namespace_bootstrap import (
    render_namespace_bootstrap,
)
from afterpush_api.services.namespace_bootstrap_readiness import (
    NamespaceBootstrapNotReady,
    verify_namespace_bootstrap,
)


PROJECT_ID = UUID("12471cf9-11d4-4089-ad0d-2c4b777fc227")


def make_api():
    expected = list(
        yaml.safe_load_all(
            render_namespace_bootstrap(
                project_id=PROJECT_ID,
                application_name="payment-api",
                environment="dev",
            )
        )
    )

    class FakeCoreAPI:
        def __init__(self):
            self.labels = deepcopy(expected[0]["metadata"]["labels"])
            self.quota = deepcopy(expected[1]["spec"]["hard"])
            self.limits = deepcopy(expected[2]["spec"]["limits"][0])
            self.missing = False

        def read_namespace(self, name):
            if self.missing:
                raise RuntimeError("Not found")
            return SimpleNamespace(
                metadata=SimpleNamespace(labels=self.labels)
            )

        def read_namespaced_resource_quota(self, name, namespace):
            return SimpleNamespace(
                spec=SimpleNamespace(hard=self.quota)
            )

        def read_namespaced_limit_range(self, name, namespace):
            item = self.limits
            return SimpleNamespace(
                spec=SimpleNamespace(
                    limits=[
                        SimpleNamespace(
                            type=item["type"],
                            default_request=item["defaultRequest"],
                            default=item["default"],
                            max=item["max"],
                            min=item["min"],
                        )
                    ]
                )
            )

    return FakeCoreAPI()


def verify(api):
    return verify_namespace_bootstrap(
        core_api=api,
        project_id=PROJECT_ID,
        application_name="payment-api",
        environment="dev",
    )


def test_ready_namespace():
    assert verify(make_api()) == f"ap-dev-{PROJECT_ID}"


def test_missing_namespace():
    api = make_api()
    api.missing = True

    with pytest.raises(NamespaceBootstrapNotReady):
        verify(api)


def test_rejects_weakened_pod_security():
    api = make_api()
    api.labels["pod-security.kubernetes.io/enforce"] = "privileged"

    with pytest.raises(NamespaceBootstrapNotReady):
        verify(api)


def test_rejects_wrong_quota():
    api = make_api()
    api.quota["pods"] = "100"

    with pytest.raises(NamespaceBootstrapNotReady):
        verify(api)


def test_rejects_wrong_limit_range():
    api = make_api()
    api.limits["max"]["memory"] = "8Gi"

    with pytest.raises(NamespaceBootstrapNotReady):
        verify(api)


def test_accepts_equivalent_cpu_quantities():
    api = make_api()

    api.quota["requests.cpu"] = "2000m"
    api.quota["limits.cpu"] = "4000m"

    api.limits["default"]["cpu"] = "0.5"
    api.limits["defaultRequest"]["cpu"] = "0.1"
    api.limits["min"]["cpu"] = "0.025"
    api.limits["max"]["cpu"] = "2000m"

    assert verify(api) == f"ap-dev-{PROJECT_ID}"


def test_accepts_equivalent_memory_quantities():
    api = make_api()

    api.quota["requests.memory"] = str(4 * 1024**3)
    api.quota["limits.memory"] = str(8 * 1024**3)

    api.limits["defaultRequest"]["memory"] = str(128 * 1024**2)
    api.limits["default"]["memory"] = str(512 * 1024**2)
    api.limits["min"]["memory"] = str(32 * 1024**2)
    api.limits["max"]["memory"] = str(2 * 1024**3)

    assert verify(api) == f"ap-dev-{PROJECT_ID}"


def test_rejects_genuinely_weaker_resource_limits():
    api = make_api()

    api.limits["max"]["cpu"] = "3"

    with pytest.raises(
        NamespaceBootstrapNotReady,
        match="LimitRange mismatch",
    ):
        verify(api)
