from pathlib import Path

import pytest

from afterpush_api.services.gitops_publication_path import (
    GitOpsPublicationPathError,
    validate_gitops_publication_path,
)


PROJECT_ID = "12471cf9-11d4-4089-ad0d-2c4b777fc227"


@pytest.mark.parametrize(
    ("path", "expected"),
    [
        (
            f"gitops/apps/dev/{PROJECT_ID}/payment-api/values.yaml",
            "deployment",
        ),
        (
            f"gitops/apps/staging/{PROJECT_ID}/payment-api/values.yaml",
            "deployment",
        ),
        (
            f"gitops/platform/namespaces/dev/{PROJECT_ID}/namespace.yaml",
            "namespace-bootstrap",
        ),
        (
            f"gitops/platform/namespaces/prod/{PROJECT_ID}/namespace.yaml",
            "namespace-bootstrap",
        ),
    ],
)
def test_accepts_approved_paths(path, expected):
    assert validate_gitops_publication_path(
        Path(path)
    ) == expected


@pytest.mark.parametrize(
    "path",
    [
        "gitops/apps/dev/not-a-uuid/payment-api/values.yaml",
        f"gitops/apps/test/{PROJECT_ID}/payment-api/values.yaml",
        f"gitops/apps/dev/{PROJECT_ID}/../values.yaml",
        f"gitops/apps/dev/{PROJECT_ID}/Payment_API/values.yaml",
        f"gitops/apps/dev/{PROJECT_ID}/payment-api/secrets.yaml",
        f"gitops/platform/namespaces/dev/not-a-uuid/namespace.yaml",
        f"gitops/platform/namespaces/dev/{PROJECT_ID}/secret.yaml",
        f"gitops/platform/rbac/dev/{PROJECT_ID}/namespace.yaml",
        "/tmp/values.yaml",
    ],
)
def test_rejects_unsafe_paths(path):
    with pytest.raises(GitOpsPublicationPathError):
        validate_gitops_publication_path(Path(path))
