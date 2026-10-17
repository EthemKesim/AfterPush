from types import SimpleNamespace
from uuid import uuid4

import pytest

from afterpush_api.services.deployment_namespace_gate import (
    NamespaceGateTarget,
    check_deployment_namespace,
)
from afterpush_api.services.namespace_bootstrap_readiness import (
    NamespaceBootstrapNotReady,
)


def make_target():
    return NamespaceGateTarget(
        project_id=uuid4(),
        application_name="payment-api",
        environment="dev",
    )


def test_gate_rejects_missing_kubernetes_client():
    with pytest.raises(NamespaceBootstrapNotReady):
        check_deployment_namespace(
            target=make_target(),
            core_api=None,
        )


def test_gate_accepts_verified_namespace():
    target = make_target()
    expected = f"ap-dev-{target.project_id}"
    calls = []

    def verifier(**kwargs):
        calls.append(kwargs)
        return expected

    actual = check_deployment_namespace(
        target=target,
        core_api=object(),
        verifier=verifier,
    )

    assert actual == expected
    assert calls[0]["project_id"] == target.project_id
    assert calls[0]["environment"] == "dev"


def test_gate_rejects_unready_namespace():
    def verifier(**kwargs):
        raise NamespaceBootstrapNotReady("Missing quota")

    with pytest.raises(NamespaceBootstrapNotReady):
        check_deployment_namespace(
            target=make_target(),
            core_api=object(),
            verifier=verifier,
        )
