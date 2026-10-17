from pathlib import Path

import yaml


MANIFEST = (
    Path(__file__).resolve().parents[2]
    / "k8s/workers/namespace-bootstrap-rbac.yaml"
)


def load_documents():
    return list(yaml.safe_load_all(MANIFEST.read_text()))


def test_manifest_contains_expected_resources():
    documents = load_documents()

    assert [document["kind"] for document in documents] == [
        "ServiceAccount",
        "ClusterRole",
        "ClusterRoleBinding",
    ]


def test_service_account_is_isolated():
    service_account = load_documents()[0]

    assert service_account["metadata"]["name"] == (
        "afterpush-namespace-bootstrap"
    )
    assert service_account["metadata"]["namespace"] == (
        "afterpush-system"
    )


def test_cluster_role_is_read_only():
    cluster_role = load_documents()[1]

    for rule in cluster_role["rules"]:
        assert rule["verbs"] == ["get"]

    resources = {
        resource
        for rule in cluster_role["rules"]
        for resource in rule["resources"]
    }

    assert resources == {
        "namespaces",
        "resourcequotas",
        "limitranges",
    }


def test_binding_targets_bootstrap_service_account():
    binding = load_documents()[2]

    assert binding["roleRef"]["name"] == (
        "afterpush-namespace-bootstrap-reader"
    )

    assert binding["subjects"] == [
        {
            "kind": "ServiceAccount",
            "name": "afterpush-namespace-bootstrap",
            "namespace": "afterpush-system",
        }
    ]
