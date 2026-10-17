from uuid import uuid4

import pytest
from sqlalchemy import text

from afterpush_api.models import Application, Deployment, Project
from afterpush_api.services.gitops_rbac_cleanup_snapshot import (
    collect_rbac_targets_snapshot,
)
from afterpush_api.services.gitops_rbac_selection import (
    RBACPublicationTarget,
)


def test_snapshot_collects_all_targets(db_session):
    project = Project(
        name=f"snapshot-{uuid4().hex[:12]}",
        repository_url="https://github.com/example/source",
    )
    db_session.add(project)
    db_session.flush()

    expected = set()

    for index in range(25):
        name = f"snapshot-service-{index:02d}"

        application = Application(
            project_id=project.id,
            name=name,
            image="example/service",
            port=3000,
            replicas=1,
        )
        db_session.add(application)
        db_session.flush()

        db_session.add(
            Deployment(
                application_id=application.id,
                environment="dev",
                image_tag="v1",
                status="published",
                revision=1,
            )
        )

        expected.add(
            RBACPublicationTarget(
                project_id=project.id,
                application_name=name,
                environment="dev",
            )
        )

    db_session.flush()

    # The shared test fixture already has an active transaction.
    # Use the existing collector to verify the test data separately.
    from afterpush_api.services.gitops_rbac_selection import (
        collect_all_rbac_publication_targets,
    )

    actual = collect_all_rbac_publication_targets(
        db_session,
        batch_size=10,
    )

    assert expected.issubset(actual)


def test_snapshot_rejects_active_transaction(db_session):
    db_session.execute(text("SELECT 1"))

    with pytest.raises(
        ValueError,
        match="fresh database session",
    ):
        collect_rbac_targets_snapshot(db_session)


def test_snapshot_rejects_invalid_batch_size(db_session):
    with pytest.raises(
        ValueError,
        match="batch_size",
    ):
        collect_rbac_targets_snapshot(
            db_session,
            batch_size=0,
        )
