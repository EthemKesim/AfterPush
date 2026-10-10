
import pytest
import yaml

from afterpush_api.services.gitops import GitOpsError
from afterpush_api.services.sync import sync_gitops_application


@pytest.fixture
def application_data(tmp_path):
    return {
        "gitops_root": tmp_path,
        "application_name": "payment-service",
        "environment": "staging",
        "image_repository": "nginx",
        "image_tag": "v1.0.0",
        "port": 3000,
        "replicas": 2,
    }


def test_sync_bootstraps_new_application(application_data):
    values_path = sync_gitops_application(**application_data)

    assert values_path.is_file()

    values = yaml.safe_load(
        values_path.read_text(encoding="utf-8")
    )

    assert values["application"]["name"] == "payment-service"
    assert values["image"]["tag"] == "v1.0.0"
    assert values["service"]["targetPort"] == 3000
    assert values["replicaCount"] == 2
    assert values["secret"]["enabled"] is False


def test_sync_updates_existing_application(application_data):
    values_path = sync_gitops_application(**application_data)

    updated_data = {
        **application_data,
        "image_tag": "v2.0.0",
    }

    sync_gitops_application(**updated_data)

    values = yaml.safe_load(
        values_path.read_text(encoding="utf-8")
    )

    assert values["image"]["tag"] == "v2.0.0"


def test_sync_preserves_existing_settings(application_data):
    values_path = sync_gitops_application(**application_data)

    values = yaml.safe_load(
        values_path.read_text(encoding="utf-8")
    )

    values["service"]["port"] = 8080
    values["ingress"]["enabled"] = True
    values["resources"]["limits"]["memory"] = "512Mi"

    values_path.write_text(
        yaml.safe_dump(values, sort_keys=False),
        encoding="utf-8",
    )

    sync_gitops_application(
        **{
            **application_data,
            "image_tag": "v3.0.0",
        }
    )

    updated_values = yaml.safe_load(
        values_path.read_text(encoding="utf-8")
    )

    assert updated_values["image"]["tag"] == "v3.0.0"
    assert updated_values["service"]["port"] == 8080
    assert updated_values["ingress"]["enabled"] is True
    assert updated_values["resources"]["limits"]["memory"] == "512Mi"


def test_sync_rejects_invalid_existing_yaml(application_data):
    values_path = sync_gitops_application(**application_data)

    values_path.write_text(
        "invalid: [yaml",
        encoding="utf-8",
    )

    original_content = values_path.read_text(encoding="utf-8")

    with pytest.raises(yaml.YAMLError):
        sync_gitops_application(
            **{
                **application_data,
                "image_tag": "v4.0.0",
            }
        )

    assert values_path.read_text(encoding="utf-8") == original_content


def test_sync_rejects_missing_image_mapping(application_data):
    values_path = sync_gitops_application(**application_data)

    values_path.write_text(
        yaml.safe_dump(
            {"application": {"name": "payment-service"}}
        ),
        encoding="utf-8",
    )

    original_content = values_path.read_text(encoding="utf-8")

    with pytest.raises(GitOpsError):
        sync_gitops_application(
            **{
                **application_data,
                "image_tag": "v5.0.0",
            }
        )

    assert values_path.read_text(encoding="utf-8") == original_content


def test_sync_separates_environments(application_data):
    staging_path = sync_gitops_application(**application_data)

    production_path = sync_gitops_application(
        **{
            **application_data,
            "environment": "production",
            "image_tag": "v1.5.0",
        }
    )

    assert staging_path != production_path

    staging_values = yaml.safe_load(
        staging_path.read_text(encoding="utf-8")
    )

    production_values = yaml.safe_load(
        production_path.read_text(encoding="utf-8")
    )

    assert staging_values["image"]["tag"] == "v1.0.0"
    assert production_values["image"]["tag"] == "v1.5.0"
