from pathlib import Path
from uuid import uuid4

import yaml

from afterpush_api.models import Application, Deployment, Project
from afterpush_api.services.deployment_worker import (
    process_pending_deployments,
)
from afterpush_api.services.gitops import get_values_path


def test_worker_applies_pending_deployment(
    db_session,
    tmp_path: Path,
):
    project = Project(
        name=f"worker-test-{uuid4().hex[:8]}",
        repository_url="https://github.com/example/project",
    )
    db_session.add(project)
    db_session.flush()

    application = Application(
        project_id=project.id,
        name="worker-service",
        image="nginx",
        port=3000,
        replicas=2,
    )
    db_session.add(application)
    db_session.flush()

    deployment = Deployment(
        application_id=application.id,
        environment="staging",
        image_tag="v1.0.0",
        status="pending",
        revision=1,
    )
    db_session.add(deployment)
    db_session.commit()

    deployment_id = deployment.id
    project_id = project.id

    results = process_pending_deployments(
        db=db_session,
        gitops_root=tmp_path,
        limit=20,
    )

    assert results["applied"] == 1
    assert results["errors"] == 0

    db_session.expire_all()

    saved_deployment = db_session.get(
        Deployment,
        deployment_id,
    )

    assert saved_deployment.status == "running"

    values_path = get_values_path(
        gitops_root=tmp_path,
        application_name="worker-service",
        environment="staging",
        project_id=project_id,
    )

    assert values_path.is_file()

    with values_path.open("r", encoding="utf-8") as file:
        values = yaml.safe_load(file)

    assert values["image"]["repository"] == "nginx"
    assert values["image"]["tag"] == "v1.0.0"
    assert values["application"]["name"] == "worker-service"


def test_worker_selects_only_latest_revision(
    db_session,
    tmp_path: Path,
):
    from afterpush_api.services.deployment_worker import (
        get_pending_deployment_ids,
    )

    project = Project(
        name=f"revision-worker-{uuid4().hex[:8]}",
        repository_url="https://github.com/example/project",
    )
    db_session.add(project)
    db_session.flush()

    application = Application(
        project_id=project.id,
        name="revision-service",
        image="nginx",
        port=3000,
        replicas=2,
    )
    db_session.add(application)
    db_session.flush()

    deployments = []

    for revision in (1, 2, 3):
        deployment = Deployment(
            application_id=application.id,
            environment="staging",
            image_tag=f"v{revision}.0.0",
            status="pending",
            revision=revision,
        )
        db_session.add(deployment)
        deployments.append(deployment)

    db_session.commit()

    latest_id = deployments[-1].id

    pending_ids = get_pending_deployment_ids(
        db=db_session,
        limit=20,
    )

    assert latest_id in pending_ids
    assert deployments[0].id not in pending_ids
    assert deployments[1].id not in pending_ids

    db_session.rollback()

    results = process_pending_deployments(
        db=db_session,
        gitops_root=tmp_path,
    )

    assert results["applied"] == 1
    assert results["errors"] == 0

    db_session.expire_all()

    assert db_session.get(
        Deployment,
        latest_id,
    ).status == "running"

    values_path = get_values_path(
        gitops_root=tmp_path,
        application_name="revision-service",
        environment="staging",
        project_id=project.id,
    )

    with values_path.open("r", encoding="utf-8") as file:
        values = yaml.safe_load(file)

    assert values["image"]["tag"] == "v3.0.0"
