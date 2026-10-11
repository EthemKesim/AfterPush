
from pathlib import Path
from unittest.mock import patch
from uuid import UUID

import pytest
import yaml

from afterpush_api.models import Application, Deployment, Project
from afterpush_api.services.deployment_orchestrator import (
    apply_deployment,
)
from afterpush_api.services.gitops import (
    get_values_path as gitops_values_path,
)


def create_consistency_deployment(db_session):
    project = Project(
        name="consistency-test-project",
        repository_url="https://github.com/example/project",
    )
    db_session.add(project)
    db_session.flush()

    application = Application(
        project_id=project.id,
        name="consistency-api",
        image="nginx",
        port=3000,
        replicas=2,
    )
    db_session.add(application)
    db_session.flush()

    deployment = Deployment(
        application_id=application.id,
        environment="staging",
        image_tag="v2.0.0",
        status="pending",
        revision=1,
    )
    db_session.add(deployment)
    db_session.commit()

    return deployment.id, project.id


def get_test_values_path(
    tmp_path: Path,
    project_id: UUID,
) -> Path:
    return gitops_values_path(
        gitops_root=tmp_path,
        application_name="consistency-api",
        environment="staging",
        project_id=project_id,
    )


def read_values(
    tmp_path: Path,
    project_id: UUID,
) -> dict:
    with get_test_values_path(
        tmp_path,
        project_id,
    ).open("r", encoding="utf-8") as file:
        return yaml.safe_load(file)


def simulate_commit_failure(
    db_session,
    deployment_id,
    tmp_path,
):
    with patch.object(
        db_session,
        "commit",
        side_effect=RuntimeError(
            "Simulated database commit failure"
        ),
    ):
        with pytest.raises(
            RuntimeError,
            match="Simulated database commit failure",
        ):
            apply_deployment(
                db=db_session,
                deployment_id=deployment_id,
                gitops_root=tmp_path,
            )


def test_commit_failure_leaves_gitops_ahead_of_database(
    db_session,
    tmp_path: Path,
):
    deployment_id, project_id = create_consistency_deployment(
        db_session
    )

    simulate_commit_failure(
        db_session,
        deployment_id,
        tmp_path,
    )

    saved = db_session.get(Deployment, deployment_id)

    assert saved is not None
    assert saved.status == "pending"

    assert get_test_values_path(
        tmp_path,
        project_id,
    ).is_file()

    assert read_values(
        tmp_path,
        project_id,
    )["image"]["tag"] == "v2.0.0"


def test_retry_recovers_after_commit_failure(
    db_session,
    tmp_path: Path,
):
    deployment_id, project_id = create_consistency_deployment(
        db_session
    )

    # First attempt: GitOps succeeds, database commit fails.
    simulate_commit_failure(
        db_session,
        deployment_id,
        tmp_path,
    )

    saved = db_session.get(Deployment, deployment_id)

    assert saved is not None
    assert saved.status == "pending"

    assert read_values(
        tmp_path,
        project_id,
    )["image"]["tag"] == "v2.0.0"

    # Second attempt: process the same deployment again.
    result = apply_deployment(
        db=db_session,
        deployment_id=deployment_id,
        gitops_root=tmp_path,
    )

    assert result == "applied"
    assert not db_session.in_transaction()

    db_session.expire_all()
    recovered = db_session.get(Deployment, deployment_id)

    assert recovered is not None
    assert recovered.status == "running"

    values = read_values(tmp_path, project_id)

    assert values["image"]["repository"] == "nginx"
    assert values["image"]["tag"] == "v2.0.0"
    assert values["replicaCount"] == 2

    # Repeating an already applied deployment must not
    # change the GitOps configuration.
    repeated_result = apply_deployment(
        db=db_session,
        deployment_id=deployment_id,
        gitops_root=tmp_path,
    )

    assert repeated_result == "invalid_status"
    assert read_values(tmp_path, project_id) == values
