from uuid import uuid4

import pytest

from afterpush_api.models import Application, Deployment, Project
from afterpush_api.services.gitops_rbac_selection import (
    RBACPublicationTarget,
    get_rbac_publication_targets,
)


def create_application(db_session, name="backend"):
    project = Project(
        name=f"rbac-selection-{uuid4().hex[:12]}",
        repository_url="https://github.com/example/source",
    )
    db_session.add(project)
    db_session.flush()

    application = Application(
        project_id=project.id,
        name=name,
        image="example/backend",
        port=3000,
        replicas=2,
    )
    db_session.add(application)
    db_session.flush()

    return application


def add_deployment(
    db_session,
    application,
    environment,
    revision,
    status,
):
    deployment = Deployment(
        application_id=application.id,
        environment=environment,
        image_tag=f"v{revision}",
        revision=revision,
        status=status,
    )
    db_session.add(deployment)
    db_session.flush()


def test_multiple_published_revisions_produce_one_target(db_session):
    application = create_application(db_session)

    add_deployment(db_session, application, "dev", 1, "published")
    add_deployment(db_session, application, "dev", 2, "published")
    add_deployment(db_session, application, "dev", 3, "published")

    targets = get_rbac_publication_targets(db_session)

    assert targets == [
        RBACPublicationTarget(
            project_id=application.project_id,
            application_name="backend",
            environment="dev",
        )
    ]


def test_different_environments_produce_separate_targets(db_session):
    application = create_application(db_session)

    add_deployment(db_session, application, "dev", 1, "published")
    add_deployment(db_session, application, "prod", 1, "published")

    targets = get_rbac_publication_targets(db_session)

    assert targets == [
        RBACPublicationTarget(
            project_id=application.project_id,
            application_name="backend",
            environment="dev",
        ),
        RBACPublicationTarget(
            project_id=application.project_id,
            application_name="backend",
            environment="prod",
        ),
    ]


def test_pending_deployments_are_not_selected(db_session):
    application = create_application(db_session)

    add_deployment(db_session, application, "dev", 1, "pending")
    add_deployment(db_session, application, "staging", 1, "publishing")

    assert get_rbac_publication_targets(db_session) == []


def test_limit_must_be_positive(db_session):
    with pytest.raises(ValueError):
        get_rbac_publication_targets(db_session, limit=0)

    with pytest.raises(ValueError):
        get_rbac_publication_targets(db_session, limit=-1)


def test_limit_restricts_number_of_targets(db_session):
    application = create_application(db_session)

    for environment in ("dev", "staging", "prod"):
        add_deployment(
            db_session,
            application,
            environment,
            1,
            "published",
        )

    targets = get_rbac_publication_targets(db_session, limit=2)

    assert len(targets) == 2
    assert [target.environment for target in targets] == [
        "dev",
        "prod",
    ]


def test_keyset_pagination_reaches_all_targets(db_session):
    project = Project(
        name=f"rbac-pagination-{uuid4().hex[:12]}",
        repository_url="https://github.com/example/source",
    )
    db_session.add(project)
    db_session.flush()

    expected_names = set()

    for index in range(25):
        name = f"service-{index:02d}"

        application = Application(
            project_id=project.id,
            name=name,
            image="example/service",
            port=3000,
            replicas=1,
        )
        db_session.add(application)
        db_session.flush()

        add_deployment(
            db_session,
            application,
            "dev",
            1,
            "published",
        )

        expected_names.add(name)

    all_targets = []
    cursor = None
    page_sizes = []

    while True:
        page = get_rbac_publication_targets(
            db_session,
            limit=10,
            after=cursor,
        )

        if not page:
            break

        page_sizes.append(len(page))
        all_targets.extend(page)
        cursor = page[-1]

    assert page_sizes == [10, 10, 5]
    assert len(all_targets) == 25
    assert len(set(all_targets)) == 25

    assert {
        target.application_name
        for target in all_targets
    } == expected_names

    assert all(
        target.project_id == project.id
        and target.environment == "dev"
        for target in all_targets
    )


def test_collect_all_rbac_targets_across_pages(db_session):
    from afterpush_api.services.gitops_rbac_selection import (
        collect_all_rbac_publication_targets,
    )

    project = Project(
        name=f"rbac-collect-{uuid4().hex[:12]}",
        repository_url="https://github.com/example/source",
    )
    db_session.add(project)
    db_session.flush()

    expected = set()

    for index in range(25):
        name = f"collect-service-{index:02d}"

        application = Application(
            project_id=project.id,
            name=name,
            image="example/service",
            port=3000,
            replicas=1,
        )
        db_session.add(application)
        db_session.flush()

        add_deployment(
            db_session,
            application,
            "dev",
            1,
            "published",
        )

        expected.add(
            RBACPublicationTarget(
                project_id=project.id,
                application_name=name,
                environment="dev",
            )
        )

    actual = collect_all_rbac_publication_targets(
        db_session,
        batch_size=10,
    )

    assert actual == expected
    assert len(actual) == 25


def test_collect_all_targets_raises_on_page_failure(
    db_session,
    monkeypatch,
):
    from afterpush_api.services import gitops_rbac_selection

    project_id = uuid4()
    calls = []

    first_page = [
        RBACPublicationTarget(
            project_id=project_id,
            application_name=f"service-{index:02d}",
            environment="dev",
        )
        for index in range(10)
    ]

    def fake_get_targets(db, limit=20, after=None):
        calls.append(after)

        if len(calls) == 1:
            return first_page

        raise RuntimeError("Simulated database query failure")

    monkeypatch.setattr(
        gitops_rbac_selection,
        "get_rbac_publication_targets",
        fake_get_targets,
    )

    with pytest.raises(
        RuntimeError,
        match="Simulated database query failure",
    ):
        gitops_rbac_selection.collect_all_rbac_publication_targets(
            db_session,
            batch_size=10,
        )

    assert len(calls) == 2
    assert calls[0] is None
    assert calls[1] == first_page[-1]


def test_collect_all_targets_rejects_invalid_batch_size(db_session):
    from afterpush_api.services.gitops_rbac_selection import (
        collect_all_rbac_publication_targets,
    )

    with pytest.raises(ValueError):
        collect_all_rbac_publication_targets(
            db_session,
            batch_size=0,
        )
