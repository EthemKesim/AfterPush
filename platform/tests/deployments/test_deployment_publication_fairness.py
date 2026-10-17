from uuid import uuid4

from afterpush_api.models import Application, Deployment, Project
from afterpush_api.services.deployment_publication_attempt import (
    record_deferred_publication_attempt,
)
from afterpush_api.services.deployment_selection import (
    get_pending_deployment_ids,
)


def _create_pending_deployment(db, *, suffix: str) -> Deployment:
    project = Project(
        name=f"fairness-project-{suffix}",
        repository_url="https://example.com/source.git",
    )
    db.add(project)
    db.flush()

    application = Application(
        project_id=project.id,
        name=f"fairness-api-{suffix}",
        image="example/fairness-api",
        port=8080,
        replicas=1,
    )
    db.add(application)
    db.flush()

    deployment = Deployment(
        application_id=application.id,
        environment="dev",
        image_tag="v1",
        image_repository=application.image,
        port=application.port,
        replicas=application.replicas,
        status="pending",
        revision=1,
    )
    db.add(deployment)
    db.flush()
    return deployment


def test_unchecked_pending_deployment_is_selected_before_deferred_retry(
    db_session,
):
    deferred = _create_pending_deployment(db_session, suffix=uuid4().hex)

    assert record_deferred_publication_attempt(
        db_session,
        deployment_id=deferred.id,
    )
    db_session.commit()

    fresh = _create_pending_deployment(db_session, suffix=uuid4().hex)
    db_session.commit()

    selected = get_pending_deployment_ids(db_session, limit=1)

    assert selected == [fresh.id]


def test_publication_retry_cooldown_does_not_block_prerequisites(
    db_session,
):
    deferred = _create_pending_deployment(db_session, suffix=uuid4().hex)

    assert record_deferred_publication_attempt(
        db_session,
        deployment_id=deferred.id,
    )
    db_session.commit()

    publication_selection = get_pending_deployment_ids(
        db_session,
        limit=1,
        respect_publication_retry=True,
    )
    prerequisite_selection = get_pending_deployment_ids(
        db_session,
        limit=1,
    )

    assert publication_selection == []
    assert prerequisite_selection == [deferred.id]
