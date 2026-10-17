from uuid import UUID

import pytest
import yaml

from afterpush_api.services.namespace_bootstrap_preparation import (
    prepare_namespace_bootstrap,
)


PROJECT_ID = UUID("12471cf9-11d4-4089-ad0d-2c4b777fc227")


def prepare(root, application_name="payment-api"):
    return prepare_namespace_bootstrap(
        repository_root=root,
        project_id=PROJECT_ID,
        application_name=application_name,
        environment="dev",
    )


def test_prepares_project_namespace(tmp_path):
    path = prepare(tmp_path)

    assert path.exists()
    assert path.relative_to(tmp_path).as_posix() == (
        f"gitops/platform/namespaces/dev/{PROJECT_ID}/namespace.yaml"
    )

    documents = list(yaml.safe_load_all(path.read_text()))
    assert [document["kind"] for document in documents] == [
        "Namespace",
        "ResourceQuota",
        "LimitRange",
    ]


def test_preparation_is_idempotent(tmp_path):
    first = prepare(tmp_path)
    original = first.read_text()

    second = prepare(tmp_path)

    assert first == second
    assert second.read_text() == original


def test_same_project_multiple_applications(tmp_path):
    first = prepare(tmp_path, "payment-api")
    second = prepare(tmp_path, "payment-worker")

    assert first == second
    assert first.read_text() == second.read_text()


def test_rejects_modified_existing_policy(tmp_path):
    path = prepare(tmp_path)
    content = path.read_text()
    path.write_text(content.replace("restricted", "privileged"))

    with pytest.raises(ValueError):
        prepare(tmp_path)


def test_rejects_invalid_environment(tmp_path):
    with pytest.raises(ValueError):
        prepare_namespace_bootstrap(
            repository_root=tmp_path,
            project_id=PROJECT_ID,
            application_name="payment-api",
            environment="production",
        )


def test_rejects_missing_repository(tmp_path):
    with pytest.raises(ValueError):
        prepare(tmp_path / "missing")


def test_rejects_invalid_project_id(tmp_path):
    with pytest.raises(TypeError):
        prepare_namespace_bootstrap(
            repository_root=tmp_path,
            project_id="not-a-uuid",
            application_name="payment-api",
            environment="dev",
        )
