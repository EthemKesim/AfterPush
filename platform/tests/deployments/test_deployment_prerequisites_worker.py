from contextlib import contextmanager
from types import SimpleNamespace
from unittest.mock import Mock, patch
from uuid import uuid4

from afterpush_api.services.deployment_prerequisites_worker import (
    process_pending_prerequisites,
)


@contextmanager
def acquired_test_lock(**kwargs):
    yield True


def test_prerequisites_batch_handles_ready_waiting_and_errors():
    project_id = uuid4()
    deployment_ids = [uuid4(), uuid4(), uuid4()]

    applications = {
        deployment_ids[0]: (
            SimpleNamespace(
                id=uuid4(),
                project_id=project_id,
                name="api-one",
            ),
            "dev",
        ),
        deployment_ids[1]: (
            SimpleNamespace(
                id=uuid4(),
                project_id=project_id,
                name="api-two",
            ),
            "dev",
        ),
        deployment_ids[2]: (
            SimpleNamespace(
                id=uuid4(),
                project_id=project_id,
                name="api-three",
            ),
            "dev",
        ),
    }

    application_by_id = {
        application.id: application
        for application, _ in applications.values()
    }

    deployments = {
        deployment_id: SimpleNamespace(
            id=deployment_id,
            application_id=application.id,
            environment=environment,
            status="pending",
        )
        for deployment_id, (application, environment)
        in applications.items()
    }

    def get_model(model, identifier):
        if model.__name__ == "Deployment":
            return deployments.get(identifier)
        if model.__name__ == "Application":
            return application_by_id.get(identifier)
        return None

    db = Mock()
    db.get.side_effect = get_model

    reconciler = Mock(
        side_effect=[
            SimpleNamespace(status="ready"),
            SimpleNamespace(status="waiting"),
            RuntimeError("GitOps unavailable"),
        ]
    )

    with (
        patch(
            "afterpush_api.services.deployment_prerequisites_worker."
            "get_pending_deployment_ids",
            return_value=deployment_ids,
        ),
        patch(
            "afterpush_api.services.deployment_prerequisites_worker."
            "try_prerequisites_lock",
            side_effect=acquired_test_lock,
        ),
        patch(
            "afterpush_api.services.deployment_prerequisites_worker."
            "is_deployment_prerequisites_eligible",
            return_value=True,
        ),
    ):
        result = process_pending_prerequisites(
            db=db,
            repository_url="https://example.com/gitops.git",
            core_api=object(),
            rbac_api=object(),
            reconciler=reconciler,
            lock_engine=object(),
        )

    assert result == {
        "ready": 1,
        "waiting": 1,
        "skipped": 0,
        "errors": 1,
    }

    assert reconciler.call_count == 3
    assert db.rollback.call_count >= 3


def test_duplicate_identity_is_processed_once():
    project_id = uuid4()
    deployment_ids = [uuid4(), uuid4()]

    application = SimpleNamespace(
        id=uuid4(),
        project_id=project_id,
        name="orders-api",
    )

    deployments = {
        deployment_id: SimpleNamespace(
            id=deployment_id,
            application_id=application.id,
            environment="dev",
            status="pending",
        )
        for deployment_id in deployment_ids
    }

    db = Mock()

    def get_model(model, identifier):
        if model.__name__ == "Deployment":
            return deployments.get(identifier)
        return application

    db.get.side_effect = get_model

    reconciler = Mock(
        return_value=SimpleNamespace(status="waiting")
    )

    with (
        patch(
            "afterpush_api.services.deployment_prerequisites_worker."
            "get_pending_deployment_ids",
            return_value=deployment_ids,
        ),
        patch(
            "afterpush_api.services.deployment_prerequisites_worker."
            "try_prerequisites_lock",
            side_effect=acquired_test_lock,
        ),
        patch(
            "afterpush_api.services.deployment_prerequisites_worker."
            "is_deployment_prerequisites_eligible",
            return_value=True,
        ),
    ):
        result = process_pending_prerequisites(
            db=db,
            repository_url="https://example.com/gitops.git",
            core_api=object(),
            rbac_api=object(),
            reconciler=reconciler,
            lock_engine=object(),
        )

    assert result["waiting"] == 1
    assert result["skipped"] == 1
    reconciler.assert_called_once()



def test_busy_lock_skips_reconciliation():
    db, deployment_id, _ = make_busy_lock_context()

    reconciler = Mock()

    @contextmanager
    def busy_lock(**kwargs):
        yield False

    with (
        patch(
            "afterpush_api.services.deployment_prerequisites_worker."
            "get_pending_deployment_ids",
            return_value=[deployment_id],
        ),
        patch(
            "afterpush_api.services.deployment_prerequisites_worker."
            "try_prerequisites_lock",
            side_effect=busy_lock,
        ),
    ):
        result = process_pending_prerequisites(
            db=db,
            repository_url="https://example.com/gitops.git",
            core_api=object(),
            rbac_api=object(),
            reconciler=reconciler,
            lock_engine=object(),
        )

    assert result["skipped"] == 1
    assert result["ready"] == 0
    assert result["waiting"] == 0
    assert result["errors"] == 0
    reconciler.assert_not_called()


def make_busy_lock_context():
    deployment_id = uuid4()
    application_id = uuid4()

    deployment = SimpleNamespace(
        id=deployment_id,
        application_id=application_id,
        environment="dev",
        status="pending",
    )

    application = SimpleNamespace(
        id=application_id,
        project_id=uuid4(),
        name="busy-api",
    )

    db = Mock()

    def get_model(model, identifier):
        if model.__name__ == "Deployment":
            return deployment
        if model.__name__ == "Application":
            return application
        return None

    db.get.side_effect = get_model

    return db, deployment_id, application



def test_ineligible_deployment_skips_reconciliation():
    db, deployment_id, _ = make_busy_lock_context()
    reconciler = Mock()

    with (
        patch(
            "afterpush_api.services.deployment_prerequisites_worker."
            "get_pending_deployment_ids",
            return_value=[deployment_id],
        ),
        patch(
            "afterpush_api.services.deployment_prerequisites_worker."
            "try_prerequisites_lock",
            side_effect=acquired_test_lock,
        ),
        patch(
            "afterpush_api.services.deployment_prerequisites_worker."
            "is_deployment_prerequisites_eligible",
            return_value=False,
        ) as eligibility_check,
    ):
        result = process_pending_prerequisites(
            db=db,
            repository_url="https://example.com/gitops.git",
            core_api=object(),
            rbac_api=object(),
            reconciler=reconciler,
            lock_engine=object(),
        )

    assert result == {
        "ready": 0,
        "waiting": 0,
        "skipped": 1,
        "errors": 0,
    }

    eligibility_check.assert_called_once_with(
        db=db,
        deployment_id=deployment_id,
    )

    reconciler.assert_not_called()
