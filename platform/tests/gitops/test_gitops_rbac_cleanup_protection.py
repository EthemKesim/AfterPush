from uuid import uuid4

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from afterpush_api.models import Base, Project, Application, Deployment
from afterpush_api.services.gitops_rbac_cleanup_protection import (
    get_rbac_cleanup_protected_targets,
    collect_all_rbac_cleanup_protected_targets,
)


@pytest.fixture
def db():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        yield session

    engine.dispose()


def create_deployment(
    db,
    *,
    project,
    application_name,
    environment,
    status,
):
    application = Application(
        id=uuid4(),
        project_id=project.id,
        name=application_name,
        image="example/app",
        port=3000,
        replicas=1,
    )

    db.add(application)
    db.flush()

    deployment = Deployment(
        id=uuid4(),
        application_id=application.id,
        environment=environment,
        image_tag="test",
        status=status,
        revision=1,
    )

    db.add(deployment)
    db.flush()

    return application


def test_all_deployment_states_are_protected(db):
    project = Project(
        id=uuid4(),
        name="cleanup-test",
        repository_url="https://example.com/repo.git",
    )
    db.add(project)
    db.flush()

    for name, status in (
        ("pending-app", "pending"),
        ("publishing-app", "publishing"),
        ("published-app", "published"),
    ):
        create_deployment(
            db,
            project=project,
            application_name=name,
            environment="dev",
            status=status,
        )

    targets = collect_all_rbac_cleanup_protected_targets(db)

    assert {target.application_name for target in targets} == {
        "pending-app",
        "publishing-app",
        "published-app",
    }


def test_duplicate_deployments_produce_one_target(db):
    project = Project(
        id=uuid4(),
        name="duplicate-test",
        repository_url="https://example.com/repo.git",
    )
    db.add(project)
    db.flush()

    application = create_deployment(
        db,
        project=project,
        application_name="example-app",
        environment="dev",
        status="published",
    )

    db.add(
        Deployment(
            id=uuid4(),
            application_id=application.id,
            environment="dev",
            image_tag="v2",
            status="publishing",
            revision=2,
        )
    )
    db.flush()

    targets = collect_all_rbac_cleanup_protected_targets(db)

    assert len(targets) == 1
    assert next(iter(targets)).application_name == "example-app"


def test_pagination_collects_every_target(db):
    project = Project(
        id=uuid4(),
        name="pagination-test",
        repository_url="https://example.com/repo.git",
    )
    db.add(project)
    db.flush()

    for index in range(25):
        create_deployment(
            db,
            project=project,
            application_name=f"app-{index:03d}",
            environment="dev",
            status="pending",
        )

    targets = collect_all_rbac_cleanup_protected_targets(
        db,
        batch_size=7,
    )

    assert len(targets) == 25
    assert {target.application_name for target in targets} == {
        f"app-{index:03d}" for index in range(25)
    }


def test_invalid_pagination_arguments(db):
    with pytest.raises(ValueError):
        get_rbac_cleanup_protected_targets(db, limit=0)

    with pytest.raises(ValueError):
        collect_all_rbac_cleanup_protected_targets(
            db,
            batch_size=0,
        )
