from uuid import UUID

import pytest
import yaml

from afterpush_api.services.namespace_bootstrap import (
    render_namespace_bootstrap,
)
from afterpush_api.services.namespace_bootstrap_validator import (
    NamespaceBootstrapValidationError,
    validate_namespace_bootstrap,
)


PROJECT_ID = UUID("12471cf9-11d4-4089-ad0d-2c4b777fc227")


def render():
    return render_namespace_bootstrap(
        project_id=PROJECT_ID,
        application_name="payment-api",
        environment="dev",
    )


def validate(content):
    validate_namespace_bootstrap(
        rendered_yaml=content,
        project_id=PROJECT_ID,
        application_name="payment-api",
        environment="dev",
    )


def test_valid_namespace_bootstrap():
    validate(render())


def test_namespace_identity():
    documents = list(yaml.safe_load_all(render()))
    assert documents[0]["metadata"]["name"] == f"ap-dev-{PROJECT_ID}"


def test_resource_quota_namespace():
    documents = list(yaml.safe_load_all(render()))
    assert documents[1]["metadata"]["namespace"] == f"ap-dev-{PROJECT_ID}"


def test_limit_range_namespace():
    documents = list(yaml.safe_load_all(render()))
    assert documents[2]["metadata"]["namespace"] == f"ap-dev-{PROJECT_ID}"


def test_rejects_missing_resource():
    documents = list(yaml.safe_load_all(render()))
    with pytest.raises(NamespaceBootstrapValidationError):
        validate(yaml.safe_dump_all(documents[:2]))


def test_rejects_extra_resource():
    documents = list(yaml.safe_load_all(render()))
    documents.append({"apiVersion": "v1", "kind": "Secret"})
    with pytest.raises(NamespaceBootstrapValidationError):
        validate(yaml.safe_dump_all(documents))


def test_rejects_weakened_pod_security():
    documents = list(yaml.safe_load_all(render()))
    documents[0]["metadata"]["labels"][
        "pod-security.kubernetes.io/enforce"
    ] = "privileged"

    with pytest.raises(NamespaceBootstrapValidationError):
        validate(yaml.safe_dump_all(documents))


def test_rejects_modified_quota():
    documents = list(yaml.safe_load_all(render()))
    documents[1]["spec"]["hard"]["pods"] = "100"

    with pytest.raises(NamespaceBootstrapValidationError):
        validate(yaml.safe_dump_all(documents))


def test_rejects_wrong_namespace():
    documents = list(yaml.safe_load_all(render()))
    documents[2]["metadata"]["namespace"] = "default"

    with pytest.raises(NamespaceBootstrapValidationError):
        validate(yaml.safe_dump_all(documents))


def test_rejects_invalid_yaml():
    with pytest.raises(NamespaceBootstrapValidationError):
        validate("kind: [invalid")


def test_rejects_invalid_environment():
    with pytest.raises(ValueError):
        render_namespace_bootstrap(
            project_id=PROJECT_ID,
            application_name="payment-api",
            environment="production",
        )
