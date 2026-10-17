import subprocess
from pathlib import Path

import yaml


PROJECT_ROOT = Path(__file__).resolve().parents[3]
CHART_PATH = PROJECT_ROOT / "helm/afterpush"


def _render(*arguments: str) -> list[dict]:
    result = subprocess.run(
        [
            "helm",
            "template",
            "payment-api",
            str(CHART_PATH),
            *arguments,
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    return [
        resource
        for resource in yaml.safe_load_all(result.stdout)
        if isinstance(resource, dict)
    ]


def test_network_policy_is_disabled_by_default():
    resources = _render()

    assert all(resource["kind"] != "NetworkPolicy" for resource in resources)


def test_network_policy_allows_only_service_port_from_selected_namespaces():
    resources = _render(
        "--set",
        "networkPolicy.enabled=true",
        "--set",
        "networkPolicy.allowedIngressNamespaces[0]=ingress-nginx",
        "--set",
        "networkPolicy.allowedIngressNamespaces[1]=monitoring",
        "--set",
        "service.targetPort=8080",
    )

    policy = next(
        resource for resource in resources if resource["kind"] == "NetworkPolicy"
    )

    assert policy["spec"]["podSelector"] == {
        "matchLabels": {"app": "afterpush-api"}
    }
    assert policy["spec"]["policyTypes"] == ["Ingress"]

    rules = policy["spec"]["ingress"]
    assert all(rule["ports"] == [{"protocol": "TCP", "port": 8080}] for rule in rules)
    assert rules[0]["from"] == [{"podSelector": {}}]
    assert rules[1]["from"][0]["namespaceSelector"]["matchLabels"] == {
        "kubernetes.io/metadata.name": "ingress-nginx"
    }
    assert rules[2]["from"][0]["namespaceSelector"]["matchLabels"] == {
        "kubernetes.io/metadata.name": "monitoring"
    }
