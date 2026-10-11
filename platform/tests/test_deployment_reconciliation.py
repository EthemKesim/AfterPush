
from pathlib import Path
from uuid import uuid4

import pytest
import yaml

from afterpush_api.models import Application, Deployment, Project
from afterpush_api.services.deployment_reconciliation import (
    check_deployment_drift,
)


def create_test_application(db_session):
    project = Project(
        name=f"reconciliation-{uuid4().hex[:8]}",
        repository_url="https://github.com/example/project",
    )
    db_session.add(project)
    db_session.flush()

    application = Application(
        project_id=project.id,
        name="reconciliation-api",
        image="nginx",
        port=3000,
        replicas=2,
    )
    db_session.add(application)
    db_session.flush()

    return application.id


def create_deployment(
    db_session,
    application_id,
    revision=1,
    image_tag="v2.0.0",
    status="running",
):
    deployment = Deployment(
        application_id=application_id,
        environment="staging",
        image_tag=image_tag,
        status=status,
        revision=revision,
    )
    db_session.add(deployment)
    db_session.flush()

    return deployment.id


def write_test_values(tmp_path: Path, image_tag: str):
    values_path = (
        tmp_path
        / "apps"
        / "staging"
        / "reconciliation-api"
        / "values.yaml"
    )

    values_path.parent.mkdir(parents=True, exist_ok=True)

    values = {
        "image": {
            "repository": "nginx",
            "tag": image_tag,
        }
    }

    with values_path.open("w", encoding="utf-8") as file:
        yaml.safe_dump(values, file, sort_keys=False)

    return values_path


def check_drift(db_session, application_id, tmp_path):
    return check_deployment_drift(
        db=db_session,
        application_id=application_id,
        environment="staging",
        gitops_root=tmp_path,
    )


def test_matching_gitops_values_are_in_sync(
    db_session,
    tmp_path: Path,
):
    application_id = create_test_application(db_session)
    create_deployment(db_session, application_id)

    write_test_values(tmp_path, "v2.0.0")

    assert check_drift(
        db_session, application_id, tmp_path
    ) == "in_sync"


def test_different_image_tag_is_detected(
    db_session,
    tmp_path: Path,
):
    application_id = create_test_application(db_session)
    create_deployment(db_session, application_id)

    write_test_values(tmp_path, "v1.0.0")

    assert check_drift(
        db_session, application_id, tmp_path
    ) == "drift_detected"


def test_missing_gitops_values_is_detected(
    db_session,
    tmp_path: Path,
):
    application_id = create_test_application(db_session)
    create_deployment(db_session, application_id)

    assert check_drift(
        db_session, application_id, tmp_path
    ) == "gitops_missing"


def test_no_applied_deployment_is_reported(
    db_session,
    tmp_path: Path,
):
    application_id = create_test_application(db_session)

    assert check_drift(
        db_session, application_id, tmp_path
    ) == "no_deployment"


def test_latest_pending_deployment_blocks_reconciliation(
    db_session,
    tmp_path: Path,
):
    application_id = create_test_application(db_session)

    create_deployment(
        db_session,
        application_id,
        revision=1,
        image_tag="v1.0.0",
        status="succeeded",
    )

    create_deployment(
        db_session,
        application_id,
        revision=2,
        image_tag="v2.0.0",
        status="running",
    )

    create_deployment(
        db_session,
        application_id,
        revision=3,
        image_tag="v3.0.0",
        status="pending",
    )

    write_test_values(tmp_path, "v2.0.0")

    assert check_drift(
        db_session, application_id, tmp_path
    ) == "deployment_pending"


def test_latest_failed_deployment_blocks_reconciliation(
    db_session,
    tmp_path: Path,
):
    application_id = create_test_application(db_session)

    create_deployment(
        db_session,
        application_id,
        revision=1,
        image_tag="v1.0.0",
        status="succeeded",
    )

    create_deployment(
        db_session,
        application_id,
        revision=2,
        image_tag="v2.0.0",
        status="failed",
    )

    write_test_values(tmp_path, "v1.0.0")

    assert check_drift(
        db_session, application_id, tmp_path
    ) == "deployment_failed"
