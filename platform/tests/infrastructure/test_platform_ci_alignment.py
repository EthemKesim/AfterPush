from pathlib import Path

import yaml


PROJECT_ROOT = Path(__file__).resolve().parents[3]


def _workflow(path: str) -> dict:
    return yaml.safe_load(
        (PROJECT_ROOT / ".github/workflows" / path).read_text()
    )


def test_ecr_delivery_builds_the_fastapi_platform_image():
    workflow = _workflow("cd-ecr.yml")
    steps = workflow["jobs"]["build-and-push"]["steps"]
    build = next(
        step
        for step in steps
        if step["name"] == "Build and push platform API image"
    )

    assert build["with"]["context"] == "./platform"
    assert build["with"]["file"] == "./platform/Dockerfile.api"
    assert "${{ github.sha }}" in build["with"]["tags"]


def test_ci_smoke_tests_the_same_fastapi_image_contract():
    workflow = _workflow("ci.yml")
    platform_steps = workflow["jobs"]["platform"]["steps"]
    build = next(
        step
        for step in platform_steps
        if step["name"] == "Build platform API image"
    )
    health = next(
        step
        for step in platform_steps
        if step["name"] == "Verify platform API container health"
    )

    assert "platform/Dockerfile.api" in build["run"]
    assert "afterpush-platform-api:ci" in build["run"]
    assert "localhost:8000/health" in health["run"]
    assert "localhost:8000/metrics" in health["run"]
    assert "afterpush_http_requests_total" in health["run"]

    scan = next(
        step
        for step in platform_steps
        if step["name"] == "Scan platform API image for vulnerabilities"
    )
    assert scan["with"]["image-ref"] == "afterpush-platform-api:ci"


def test_ecr_delivery_emits_build_provenance_and_sbom():
    workflow = _workflow("cd-ecr.yml")
    steps = workflow["jobs"]["build-and-push"]["steps"]
    build = next(
        step
        for step in steps
        if step["name"] == "Build and push platform API image"
    )

    assert build["with"]["provenance"] is True
    assert build["with"]["sbom"] is True


def test_ecr_delivery_builds_a_separate_runtime_worker_image():
    workflow = _workflow("cd-ecr.yml")
    steps = workflow["jobs"]["build-and-push"]["steps"]
    build = next(
        step
        for step in steps
        if step["name"] == "Build and push runtime worker image"
    )

    assert build["with"]["context"] == "./platform"
    assert build["with"]["file"] == "./platform/Dockerfile.runtime-worker"
    assert "ECR_RUNTIME_WORKER_REPOSITORY" in build["with"]["tags"]
    assert build["with"]["provenance"] is True
    assert build["with"]["sbom"] is True


def test_ci_builds_and_scans_the_runtime_worker_image():
    workflow = _workflow("ci.yml")
    platform_steps = workflow["jobs"]["platform"]["steps"]
    build = next(
        step
        for step in platform_steps
        if step["name"] == "Build runtime reconciliation worker image"
    )
    command = next(
        step
        for step in platform_steps
        if step["name"] == "Verify runtime worker command contract"
    )
    scan = next(
        step
        for step in platform_steps
        if step["name"] == "Scan runtime worker image for vulnerabilities"
    )

    assert "platform/Dockerfile.runtime-worker" in build["run"]
    assert "afterpush-runtime-worker:ci" in command["run"]
    assert "deployment_runtime_reconciliation" in command["run"]
    assert scan["with"]["image-ref"] == "afterpush-runtime-worker:ci"


def test_ci_validates_each_terraform_state_root():
    workflow = _workflow("ci.yml")
    terraform_steps = workflow["jobs"]["terraform"]["steps"]

    expected_validations = {
        "terraform": (
            "Initialize Terraform",
            "Validate Terraform configuration",
        ),
        "terraform/shared": (
            "Initialize shared Terraform configuration",
            "Validate shared Terraform configuration",
        ),
        "terraform/eks": (
            "Initialize EKS Terraform configuration",
            "Validate EKS Terraform configuration",
        ),
    }

    for directory, (init_name, validate_name) in expected_validations.items():
        init_step = next(step for step in terraform_steps if step["name"] == init_name)
        validate_step = next(
            step for step in terraform_steps if step["name"] == validate_name
        )

        assert init_step.get("working-directory", "terraform") == directory
        assert init_step["run"] == "terraform init -backend=false"
        assert validate_step.get("working-directory", "terraform") == directory
        assert validate_step["run"] == "terraform validate"


def test_platform_application_examples_match_fastapi_listen_port():
    for path in (
        "platform/examples/afterpush.yaml",
        "platform/environments/eks/afterpush.yaml",
    ):
        configuration = yaml.safe_load((PROJECT_ROOT / path).read_text())
        assert configuration["spec"]["port"] == 8000
