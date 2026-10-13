
import hashlib
import re
from pathlib import Path

import yaml


PROJECT_ROOT = Path(__file__).resolve().parents[3]

ARGOCD_PATH = PROJECT_ROOT / "argocd/applications"

LEGACY_APPLICATIONSET = (
    ARGOCD_PATH / "afterpush-applicationset.yaml"
)

PROJECT_APPLICATIONSET = (
    ARGOCD_PATH / "afterpush-project-applicationset.yaml"
)

PROJECT_A = "123e4567-e89b-12d3-a456-426614174000"
PROJECT_B = "123e4567-e89b-12d3-a456-426614174001"


def load_applicationset(path: Path) -> dict:
    with path.open(encoding="utf-8") as file:
        return yaml.safe_load(file)


def build_expected_application_name(
    environment: str,
    project_id: str,
    application_name: str,
) -> str:
    """
    Model the ApplicationSet naming convention.

    This checks our expected naming behavior; it does not
    execute the Argo CD Go template engine.
    """
    gitops_path = (
        f"gitops/apps/{environment}/"
        f"{project_id}/{application_name}"
    )

    identity_hash = hashlib.sha256(
        gitops_path.encode("utf-8")
    ).hexdigest()[:12]

    return f"ap-{environment}-{identity_hash}"


def test_legacy_and_project_applicationsets_are_separate():
    legacy = load_applicationset(LEGACY_APPLICATIONSET)
    project = load_applicationset(PROJECT_APPLICATIONSET)

    assert legacy["kind"] == "ApplicationSet"
    assert project["kind"] == "ApplicationSet"

    assert legacy["metadata"]["name"] == "afterpush-apps"
    assert project["metadata"]["name"] == "afterpush-project-apps"

    assert legacy["metadata"]["name"] != project["metadata"]["name"]


def test_project_applicationset_discovers_project_directories():
    applicationset = load_applicationset(
        PROJECT_APPLICATIONSET
    )

    generator = applicationset["spec"]["generators"][0]["git"]

    assert generator["revision"] == "main"

    assert generator["directories"] == [
        {"path": "gitops/apps/*/*/*"}
    ]


def test_project_applicationset_uses_project_values_file():
    applicationset = load_applicationset(
        PROJECT_APPLICATIONSET
    )

    sources = applicationset["spec"]["template"]["spec"]["sources"]

    helm_source = sources[0]
    values_source = sources[1]

    assert helm_source["path"] == "helm/afterpush"

    assert helm_source["helm"]["valueFiles"] == [
        "$values/{{ .path.path }}/values.yaml"
    ]

    assert values_source["ref"] == "values"


def test_project_applicationset_uses_project_namespace():
    applicationset = load_applicationset(
        PROJECT_APPLICATIONSET
    )

    destination = applicationset["spec"]["template"]["spec"][
        "destination"
    ]

    assert destination["server"] == (
        "https://kubernetes.default.svc"
    )

    assert destination["namespace"] == (
        "ap-{{ index .path.segments 2 }}-"
        "{{ index .path.segments 3 }}"
    )


def test_project_applicationset_uses_hashed_application_identity():
    applicationset = load_applicationset(
        PROJECT_APPLICATIONSET
    )

    application_name = applicationset["spec"]["template"][
        "metadata"
    ]["name"]

    assert application_name == (
        "ap-{{ index .path.segments 2 }}-"
        "{{ .path.path | sha256sum | trunc 12 }}"
    )


def test_application_names_are_stable_and_distinct():
    first = build_expected_application_name(
        "staging",
        PROJECT_A,
        "backend-api",
    )

    repeated = build_expected_application_name(
        "staging",
        PROJECT_A,
        "backend-api",
    )

    other_project = build_expected_application_name(
        "staging",
        PROJECT_B,
        "backend-api",
    )

    other_application = build_expected_application_name(
        "staging",
        PROJECT_A,
        "backend-worker",
    )

    other_environment = build_expected_application_name(
        "production",
        PROJECT_A,
        "backend-api",
    )

    assert first == repeated

    assert len({
        first,
        other_project,
        other_application,
        other_environment,
    }) == 4


def test_long_application_names_produce_short_argocd_names():
    long_application_name = "backend-" + ("service-" * 20)

    result = build_expected_application_name(
        "staging",
        PROJECT_A,
        long_application_name,
    )

    assert len(result) <= 63

    assert re.fullmatch(
        r"[a-z0-9]([-a-z0-9]*[a-z0-9])?",
        result,
    )


def test_application_name_respects_maximum_environment_length():
    # Project environments are limited to 23 characters
    # by GitOps namespace validation.
    environment = "a" * 23

    result = build_expected_application_name(
        environment,
        PROJECT_A,
        "backend-api",
    )

    assert len(result) <= 63


def test_project_applicationset_enables_namespace_creation():
    applicationset = load_applicationset(
        PROJECT_APPLICATIONSET
    )

    sync_policy = applicationset["spec"]["template"]["spec"][
        "syncPolicy"
    ]

    assert sync_policy["automated"]["prune"] is True
    assert sync_policy["automated"]["selfHeal"] is True

    assert "CreateNamespace=true" in (
        sync_policy["syncOptions"]
    )


def test_legacy_applicationset_preserves_existing_gitops_path():
    applicationset = load_applicationset(
        LEGACY_APPLICATIONSET
    )

    generator = applicationset["spec"]["generators"][0]["git"]

    assert generator["directories"] == [
        {"path": "gitops/apps/afterpush-api"}
    ]

    assert applicationset["spec"]["template"]["spec"][
        "destination"
    ]["namespace"] == "afterpush-dev"
