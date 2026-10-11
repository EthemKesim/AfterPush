
from pathlib import Path
from uuid import UUID, uuid4

import pytest
import yaml

from afterpush_api.models import Application, Deployment, Project
from afterpush_api.services.deployment_orchestrator import (
    apply_deployment,
)
from afterpush_api.services.gitops import (
    GitOpsError,
    get_values_path,
)


def create_test_application(db_session):
    project = Project(
        name=f"orchestrator-test-{uuid4().hex[:8]}",
        repository_url="https://github.com/example/project",
    )
    db_session.add(project)
    db_session.flush()

    application = Application(
        project_id=project.id,
        name="payment-service",
        image="nginx",
        port=3000,
        replicas=2,
    )
    db_session.add(application)
    db_session.flush()

    return application


def get_test_values_path(
    tmp_path: Path,
    project_id: UUID,
) -> Path:
    return get_values_path(
        gitops_root=tmp_path,
        application_name="payment-service",
        environment="staging",
        project_id=project_id,
    )


def read_test_values(
    tmp_path: Path,
    project_id: UUID,
) -> dict:
    with get_test_values_path(
        tmp_path,
        project_id,
    ).open("r", encoding="utf-8") as file:
        return yaml.safe_load(file)


def test_older_deployment_is_skipped(db_session, tmp_path: Path):
    application = create_test_application(db_session)
    project_id = application.project_id

    older = Deployment(
        application_id=application.id,
        environment="staging",
        image_tag="v1.0.0",
        status="pending",
        revision=1,
    )
    newer = Deployment(
        application_id=application.id,
        environment="staging",
        image_tag="v2.0.0",
        status="pending",
        revision=2,
    )

    db_session.add_all([older, newer])
    db_session.commit()

    older_id = older.id

    result = apply_deployment(
        db=db_session,
        deployment_id=older_id,
        gitops_root=tmp_path,
    )

    assert result == "skipped"
    assert not db_session.in_transaction()
    assert not get_test_values_path(
        tmp_path,
        project_id,
    ).exists()

    saved = db_session.get(Deployment, older_id)
    assert saved is not None
    assert saved.status == "pending"


def test_latest_deployment_is_applied(db_session, tmp_path: Path):
    application = create_test_application(db_session)
    project_id = application.project_id

    deployment = Deployment(
        application_id=application.id,
        environment="staging",
        image_tag="v2.0.0",
        status="pending",
        revision=1,
    )

    db_session.add(deployment)
    db_session.commit()

    deployment_id = deployment.id

    result = apply_deployment(
        db=db_session,
        deployment_id=deployment_id,
        gitops_root=tmp_path,
    )

    assert result == "applied"
    assert not db_session.in_transaction()

    saved = db_session.get(Deployment, deployment_id)
    assert saved is not None
    assert saved.status == "running"

    values = read_test_values(tmp_path, project_id)
    assert values["application"]["name"] == "payment-service"
    assert values["image"]["repository"] == "nginx"
    assert values["image"]["tag"] == "v2.0.0"
    assert values["replicaCount"] == 2


def test_new_revision_updates_existing_gitops_values(
    db_session,
    tmp_path: Path,
):
    application = create_test_application(db_session)
    application_id = application.id
    project_id = application.project_id

    first = Deployment(
        application_id=application_id,
        environment="staging",
        image_tag="v1.0.0",
        status="pending",
        revision=1,
    )

    db_session.add(first)
    db_session.commit()

    first_id = first.id

    assert apply_deployment(
        db=db_session,
        deployment_id=first_id,
        gitops_root=tmp_path,
    ) == "applied"

    initial_values = read_test_values(tmp_path, project_id)
    assert initial_values["image"]["tag"] == "v1.0.0"

    initial_values["config"]["logLevel"] = "debug"
    initial_values["service"]["port"] = 8080

    with get_test_values_path(
        tmp_path,
        project_id,
    ).open("w", encoding="utf-8") as file:
        yaml.safe_dump(initial_values, file, sort_keys=False)

    second = Deployment(
        application_id=application_id,
        environment="staging",
        image_tag="v2.0.0",
        status="pending",
        revision=2,
    )

    db_session.add(second)
    db_session.commit()

    second_id = second.id

    assert apply_deployment(
        db=db_session,
        deployment_id=second_id,
        gitops_root=tmp_path,
    ) == "applied"

    updated = read_test_values(tmp_path, project_id)

    assert updated["image"]["repository"] == "nginx"
    assert updated["image"]["tag"] == "v2.0.0"
    assert updated["replicaCount"] == 2
    assert updated["config"]["logLevel"] == "debug"
    assert updated["service"]["port"] == 8080
    assert updated["service"]["targetPort"] == 3000

    assert apply_deployment(
        db=db_session,
        deployment_id=first_id,
        gitops_root=tmp_path,
    ) == "invalid_status"

    assert not db_session.in_transaction()
    assert read_test_values(
        tmp_path,
        project_id,
    )["image"]["tag"] == "v2.0.0"


def test_gitops_failure_keeps_deployment_pending(
    db_session,
    tmp_path: Path,
):
    application = create_test_application(db_session)
    project_id = application.project_id

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

    values_path = get_test_values_path(
        tmp_path,
        project_id,
    )
    values_path.parent.mkdir(parents=True, exist_ok=True)
    values_path.write_text(
        "image: invalid-image-structure\n",
        encoding="utf-8",
    )

    with pytest.raises(GitOpsError):
        apply_deployment(
            db=db_session,
            deployment_id=deployment_id,
            gitops_root=tmp_path,
        )

    assert not db_session.in_transaction()

    saved = db_session.get(Deployment, deployment_id)
    assert saved is not None
    assert saved.status == "pending"

    assert values_path.read_text(
        encoding="utf-8"
    ) == "image: invalid-image-structure\n"


def test_missing_deployment_closes_transaction(
    db_session,
    tmp_path: Path,
):
    result = apply_deployment(
        db=db_session,
        deployment_id=uuid4(),
        gitops_root=tmp_path,
    )

    assert result == "not_found"
    assert not db_session.in_transaction()
