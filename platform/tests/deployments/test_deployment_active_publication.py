from uuid import uuid4

from afterpush_api.models import Application, Deployment, Project
from afterpush_api.services.deployment_claim import claim_deployment


def test_newer_deployment_waits_for_active_publication(db_session):
    project = Project(
        name=f"active-publication-{uuid4().hex[:8]}",
        repository_url="https://github.com/example/project",
    )
    db_session.add(project)
    db_session.flush()

    application = Application(
        project_id=project.id,
        name="test-api",
        image="example/test-api",
        port=3000,
        replicas=2,
    )
    db_session.add(application)
    db_session.flush()

    older = Deployment(
        application_id=application.id,
        environment="dev",
        image_tag="v11",
        revision=11,
        status="publishing",
        publication_claim_id=uuid4(),
    )

    newer = Deployment(
        application_id=application.id,
        environment="dev",
        image_tag="v12",
        revision=12,
        status="pending",
    )

    db_session.add_all([older, newer])
    db_session.flush()

    assert claim_deployment(db_session, newer.id) is None

    db_session.refresh(newer)
    assert newer.status == "pending"

    older.status = "published"
    older.publication_claim_id = None
    db_session.flush()

    claim_id = claim_deployment(db_session, newer.id)

    assert claim_id is not None

    db_session.refresh(newer)
    assert newer.status == "publishing"
    assert newer.publication_claim_id == claim_id
