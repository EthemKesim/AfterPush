from uuid import uuid4

from afterpush_api.models import Application, Project
from afterpush_api.services.deployment_revision import (
    create_versioned_deployment,
)


def test_deployment_snapshots_application_settings(db_session):
    project = Project(
        name=f"snapshot-{uuid4().hex[:8]}",
        repository_url="https://example.com/snapshot.git",
    )
    db_session.add(project)
    db_session.flush()

    application = Application(
        project_id=project.id,
        name="snapshot-api",
        image="registry.example/snapshot-api",
        port=3000,
        replicas=2,
    )
    db_session.add(application)
    db_session.flush()

    deployment = create_versioned_deployment(
        db_session,
        application_id=application.id,
        environment="dev",
        image_tag="v1",
    )
    assert deployment is not None

    application.image = "registry.example/snapshot-api-renamed"
    application.port = 8080
    application.replicas = 4
    db_session.flush()
    db_session.refresh(deployment)

    assert deployment.image_repository == "registry.example/snapshot-api"
    assert deployment.image_tag == "v1"
    assert deployment.port == 3000
    assert deployment.replicas == 2
