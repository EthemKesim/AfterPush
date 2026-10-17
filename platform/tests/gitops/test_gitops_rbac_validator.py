from uuid import uuid4

import pytest
import yaml

from afterpush_api.services.gitops_rbac_preparation import (
    prepare_gitops_rbac,
)
from afterpush_api.services.gitops_rbac_validator import (
    GitOpsRBACValidationError,
    validate_gitops_rbac,
)


@pytest.fixture
def rbac_case(tmp_path):
    project_id = uuid4()
    application_name = "payment-api"
    environment = "dev"

    paths = prepare_gitops_rbac(
        repository_root=tmp_path,
        project_id=project_id,
        application_name=application_name,
        environment=environment,
    )

    return {
        "paths": paths,
        "project_id": project_id,
        "application_name": application_name,
        "environment": environment,
    }


def validate(case):
    validate_gitops_rbac(
        rbac_paths=case["paths"],
        project_id=case["project_id"],
        application_name=case["application_name"],
        environment=case["environment"],
    )


def modify_role(case, filename, change):
    path = next(
        path for path in case["paths"]
        if path.name == filename
    )

    documents = list(yaml.safe_load_all(path.read_text()))
    change(documents[0])

    path.write_text(
        yaml.safe_dump_all(documents, sort_keys=False),
        encoding="utf-8",
    )


def test_valid_rbac_is_accepted(rbac_case):
    validate(rbac_case)


@pytest.mark.parametrize(
    "verb",
    ["list", "watch", "delete", "create", "update"],
)
def test_extra_permissions_are_rejected(rbac_case, verb):
    modify_role(
        rbac_case,
        "deployment-rbac.yaml",
        lambda role: role["rules"][0]["verbs"].append(verb),
    )

    with pytest.raises(GitOpsRBACValidationError):
        validate(rbac_case)


def test_missing_resource_restriction_is_rejected(rbac_case):
    modify_role(
        rbac_case,
        "deployment-rbac.yaml",
        lambda role: role["rules"][0].pop("resourceNames"),
    )

    with pytest.raises(GitOpsRBACValidationError):
        validate(rbac_case)


def test_extra_rbac_rule_is_rejected(rbac_case):
    modify_role(
        rbac_case,
        "deployment-rbac.yaml",
        lambda role: role["rules"].append({
            "apiGroups": [""],
            "resources": ["secrets"],
            "verbs": ["get"],
        }),
    )

    with pytest.raises(GitOpsRBACValidationError):
        validate(rbac_case)


def test_argocd_permissions_cannot_expand(rbac_case):
    modify_role(
        rbac_case,
        "argocd-rbac.yaml",
        lambda role: role["rules"][0]["verbs"].append("list"),
    )

    with pytest.raises(GitOpsRBACValidationError):
        validate(rbac_case)


def test_wrong_service_account_is_rejected(rbac_case):
    path = next(
        path for path in rbac_case["paths"]
        if path.name == "deployment-rbac.yaml"
    )

    documents = list(yaml.safe_load_all(path.read_text()))
    documents[1]["subjects"][0]["name"] = "default"

    path.write_text(
        yaml.safe_dump_all(documents, sort_keys=False),
        encoding="utf-8",
    )

    with pytest.raises(GitOpsRBACValidationError):
        validate(rbac_case)


def test_additional_yaml_document_is_rejected(rbac_case):
    path = next(
        path for path in rbac_case["paths"]
        if path.name == "argocd-rbac.yaml"
    )

    documents = list(yaml.safe_load_all(path.read_text()))
    documents.append({
        "apiVersion": "v1",
        "kind": "Secret",
        "metadata": {"name": "unexpected"},
    })

    path.write_text(
        yaml.safe_dump_all(documents, sort_keys=False),
        encoding="utf-8",
    )

    with pytest.raises(GitOpsRBACValidationError):
        validate(rbac_case)
