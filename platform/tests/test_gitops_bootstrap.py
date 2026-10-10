
import pytest
import yaml

from afterpush_api.services.bootstrap import (
    GitOpsBootstrapError,
    bootstrap_gitops_application,
)


def test_bootstrap_creates_values_file(tmp_path):
    values_path = bootstrap_gitops_application(
        gitops_root=tmp_path,
        application_name="payment-service",
        environment="staging",
        image_repository="nginx",
        image_tag="v1.0.0",
        port=3000,
        replicas=2,
    )

    assert values_path.is_file()

    values = yaml.safe_load(
        values_path.read_text(encoding="utf-8")
    )

    assert values["application"]["name"] == "payment-service"
    assert values["environment"]["name"] == "staging"
    assert values["image"]["repository"] == "nginx"
    assert values["image"]["tag"] == "v1.0.0"
    assert values["service"]["targetPort"] == 3000
    assert values["replicaCount"] == 2
    assert values["autoscaling"]["enabled"] is False


def test_bootstrap_does_not_overwrite_existing_values(tmp_path):
    arguments = {
        "gitops_root": tmp_path,
        "application_name": "payment-service",
        "environment": "staging",
        "image_repository": "nginx",
        "image_tag": "v1.0.0",
        "port": 3000,
        "replicas": 2,
    }

    values_path = bootstrap_gitops_application(**arguments)
    original_content = values_path.read_text(encoding="utf-8")

    with pytest.raises(GitOpsBootstrapError):
        bootstrap_gitops_application(
            **{
                **arguments,
                "image_tag": "v2.0.0",
            }
        )

    assert values_path.read_text(encoding="utf-8") == original_content


@pytest.mark.parametrize(
    "port",
    [0, -1, 65536],
)
def test_bootstrap_rejects_invalid_port(tmp_path, port):
    with pytest.raises(GitOpsBootstrapError):
        bootstrap_gitops_application(
            gitops_root=tmp_path,
            application_name="payment-service",
            environment="staging",
            image_repository="nginx",
            image_tag="v1.0.0",
            port=port,
            replicas=2,
        )


def test_bootstrap_rejects_invalid_replicas(tmp_path):
    with pytest.raises(GitOpsBootstrapError):
        bootstrap_gitops_application(
            gitops_root=tmp_path,
            application_name="payment-service",
            environment="staging",
            image_repository="nginx",
            image_tag="v1.0.0",
            port=3000,
            replicas=0,
        )


def test_bootstrap_separates_environments(tmp_path):
    common_arguments = {
        "gitops_root": tmp_path,
        "application_name": "payment-service",
        "image_repository": "nginx",
        "image_tag": "v1.0.0",
        "port": 3000,
        "replicas": 2,
    }

    dev_path = bootstrap_gitops_application(
        **common_arguments,
        environment="dev",
    )

    staging_path = bootstrap_gitops_application(
        **common_arguments,
        environment="staging",
    )

    assert dev_path != staging_path
    assert dev_path.is_file()
    assert staging_path.is_file()
