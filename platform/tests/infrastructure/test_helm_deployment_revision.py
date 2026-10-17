import subprocess
from pathlib import Path

import yaml


CHART_PATH = Path(__file__).resolve().parents[2].parent / "helm" / "afterpush"


def render_deployment(*extra_args: str) -> dict:
    result = subprocess.run(
        [
            "helm",
            "template",
            "afterpush-test",
            str(CHART_PATH),
            "--show-only",
            "templates/deployment.yaml",
            *extra_args,
        ],
        capture_output=True,
        text=True,
        check=True,
    )

    deployment = yaml.safe_load(result.stdout)

    assert deployment["kind"] == "Deployment"

    return deployment


def test_revision_annotation_is_added_to_deployment_and_pod_template():
    deployment = render_deployment(
        "--set",
        "deployment.revision=5",
    )

    metadata_annotations = deployment["metadata"]["annotations"]

    pod_annotations = deployment["spec"]["template"]["metadata"]["annotations"]

    assert metadata_annotations["afterpush.dev/revision"] == "5"
    assert pod_annotations["afterpush.dev/revision"] == "5"

    assert "checksum/config" in pod_annotations


def test_revision_annotation_is_absent_without_revision():
    deployment = render_deployment()

    metadata_annotations = deployment["metadata"].get("annotations", {})

    pod_annotations = deployment["spec"]["template"]["metadata"]["annotations"]

    assert "afterpush.dev/revision" not in metadata_annotations
    assert "afterpush.dev/revision" not in pod_annotations

    assert "checksum/config" in pod_annotations


def test_revision_change_updates_pod_template():
    first = render_deployment(
        "--set",
        "deployment.revision=5",
    )

    second = render_deployment(
        "--set",
        "deployment.revision=6",
    )

    first_template = first["spec"]["template"]
    second_template = second["spec"]["template"]

    assert first_template != second_template

    assert (
        first_template["metadata"]["annotations"]["afterpush.dev/revision"]
        == "5"
    )

    assert (
        second_template["metadata"]["annotations"]["afterpush.dev/revision"]
        == "6"
    )
