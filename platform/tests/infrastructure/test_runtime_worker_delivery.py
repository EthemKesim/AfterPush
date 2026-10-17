from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[3]


def test_shared_infrastructure_declares_an_immutable_worker_repository():
    ecr = (PROJECT_ROOT / "terraform/shared/ecr.tf").read_text()

    assert 'resource "aws_ecr_repository" "runtime_worker"' in ecr
    assert 'name                 = "afterpush-runtime-worker"' in ecr
    assert 'image_tag_mutability = "IMMUTABLE"' in ecr
    assert "prevent_destroy = true" in ecr


def test_github_oidc_policy_can_push_only_to_declared_worker_repository():
    policy = (PROJECT_ROOT / "terraform/shared/github_oidc.tf").read_text()

    assert "aws_ecr_repository.runtime_worker.arn" in policy
