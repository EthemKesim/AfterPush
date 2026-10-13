from datetime import datetime, timedelta, timezone
from uuid import uuid4

from afterpush_api.models import Application, Deployment, Project
from afterpush_api.services.deployment_recovery import (
    get_stale_publications,
)


def test_recovery_detects_only_expired_publications(db_session):
    project = Project(
        name=f"recovery-{uuid4().hex[:8]}",
        repository_url="https://github.com/example/source",
    )
    db_session.add(project)
    db_session.flush()

    application = Application(
        project_id=project.id,
        name="recovery-api",
        image="example/recovery-api",
        port=3000,
        replicas=2,
    )
    db_session.add(application)
    db_session.flush()

    now = datetime.now(timezone.utc)

    stale = Deployment(
        application_id=application.id,
        environment="dev",
        image_tag="v1",
        revision=1,
        status="publishing",
        publication_claim_id=uuid4(),
        publication_claimed_at=now - timedelta(minutes=30),
    )

    recent = Deployment(
        application_id=application.id,
        environment="staging",
        image_tag="v2",
        revision=1,
        status="publishing",
        publication_claim_id=uuid4(),
        publication_claimed_at=now - timedelta(minutes=2),
    )

    pending = Deployment(
        application_id=application.id,
        environment="production",
        image_tag="v3",
        revision=1,
        status="pending",
    )

    db_session.add_all([stale, recent, pending])
    db_session.flush()

    results = get_stale_publications(
        db=db_session,
        timeout_minutes=15,
    )

    result_ids = {deployment.id for deployment in results}

    assert stale.id in result_ids
    assert recent.id not in result_ids
    assert pending.id not in result_ids

    db_session.refresh(stale)
    assert stale.status == "publishing"
    assert stale.publication_claim_id is not None
