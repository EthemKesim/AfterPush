
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


def load_applicationset(path: Path) -> dict:
    with path.open(encoding="utf-8") as file:
        return yaml.safe_load(file)


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


def test_project_applicationset_uses_unique_application_identity():
    applicationset = load_applicationset(
        PROJECT_APPLICATIONSET
    )

    application_name = applicationset["spec"]["template"][
        "metadata"
    ]["name"]

    assert "index .path.segments 2" in application_name
    assert "index .path.segments 3" in application_name
    assert "index .path.segments 4" in application_name


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
