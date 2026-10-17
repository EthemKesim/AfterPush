from uuid import uuid4

import pytest

from afterpush_api.models import Application, Deployment, Project
from afterpush_api.services import gitops_rbac_reconciler
from afterpush_api.services.gitops_rbac_reconciler import (
    reconcile_published_rbac,
)


def create_published_targets(db_session, count):
    project = Project(
        name=f"rbac-reconciler-{uuid4().hex[:12]}",
        repository_url="https://github.com/example/source",
    )
    db_session.add(project)
    db_session.flush()

    for index in range(count):
        application = Application(
            project_id=project.id,
            name=f"service-{index:02d}",
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
                revision=1,
                status="published",
            )
        )

    db_session.flush()
    return project


def test_reconciler_processes_all_paginated_targets(
    db_session,
    monkeypatch,
):
    project = create_published_targets(db_session, 25)
    calls = []

    def fake_publish(**kwargs):
        calls.append(kwargs)
        return "test-commit-sha"

    monkeypatch.setattr(
        gitops_rbac_reconciler,
        "publish_rbac_with_retry",
        fake_publish,
    )

    result = reconcile_published_rbac(
        db=db_session,
        repository_url="https://example.com/gitops.git",
        batch_size=10,
    )

    assert result.processed == 25
    assert result.succeeded == 25
    assert result.failed == 0
    assert result.failed_targets == []
    assert len(calls) == 25

    assert {
        call["application_name"] for call in calls
    } == {
        f"service-{index:02d}" for index in range(25)
    }

    assert all(
        call["project_id"] == project.id
        and call["environment"] == "dev"
        for call in calls
    )


def test_reconciler_continues_after_publication_failure(
    db_session,
    monkeypatch,
):
    create_published_targets(db_session, 5)
    calls = []

    def fake_publish(**kwargs):
        name = kwargs["application_name"]
        calls.append(name)

        if name == "service-02":
            raise RuntimeError("Simulated Git push failure")

        return "test-commit-sha"

    monkeypatch.setattr(
        gitops_rbac_reconciler,
        "publish_rbac_with_retry",
        fake_publish,
    )

    result = reconcile_published_rbac(
        db=db_session,
        repository_url="https://example.com/gitops.git",
        batch_size=2,
    )

    assert result.processed == 5
    assert result.succeeded == 4
    assert result.failed == 1
    assert len(result.failed_targets) == 1
    assert result.failed_targets[0].application_name == "service-02"

    assert calls == [
        "service-00",
        "service-01",
        "service-02",
        "service-03",
        "service-04",
    ]


def test_reconciler_rejects_invalid_batch_size(db_session):
    with pytest.raises(ValueError):
        reconcile_published_rbac(
            db=db_session,
            repository_url="https://example.com/gitops.git",
            batch_size=0,
        )
