
import multiprocessing
from pathlib import Path
from uuid import uuid4

import yaml

from afterpush_api.models import Application, Deployment, Project
from afterpush_api.services.deployment_reconciliation import (
    check_deployment_drift,
)
from afterpush_api.services.locking import gitops_application_lock


def hold_gitops_lock(root, locked, release):
    with gitops_application_lock(
        gitops_root=Path(root),
        application_name="reconciliation-api",
        environment="staging",
    ):
        locked.set()

        if not release.wait(timeout=10):
            raise TimeoutError("Lock release was not signaled")


def prepare_reconciliation_data(db_session, tmp_path):
    project = Project(
        name=f"lock-test-{uuid4().hex[:8]}",
        repository_url="https://github.com/example/project",
    )
    db_session.add(project)
    db_session.flush()

    application = Application(
        project_id=project.id,
        name="reconciliation-api",
        image="nginx",
        port=3000,
        replicas=2,
    )
    db_session.add(application)
    db_session.flush()

    deployment = Deployment(
        application_id=application.id,
        environment="staging",
        image_tag="v2.0.0",
        status="running",
        revision=1,
    )
    db_session.add(deployment)
    db_session.flush()

    values_path = (
        tmp_path
        / "apps"
        / "staging"
        / "reconciliation-api"
        / "values.yaml"
    )
    values_path.parent.mkdir(parents=True, exist_ok=True)

    with values_path.open("w", encoding="utf-8") as file:
        yaml.safe_dump(
            {"image": {"repository": "nginx", "tag": "v2.0.0"}},
            file,
        )

    return application.id


def test_reconciliation_waits_for_gitops_lock(
    db_session,
    tmp_path,
):
    application_id = prepare_reconciliation_data(
        db_session, tmp_path
    )

    context = multiprocessing.get_context("spawn")
    locked = context.Event()
    release = context.Event()

    process = context.Process(
        target=hold_gitops_lock,
        args=(str(tmp_path), locked, release),
    )

    process.start()

    try:
        assert locked.wait(timeout=5), "Worker did not acquire lock"

        release.set()

        result = check_deployment_drift(
            db=db_session,
            application_id=application_id,
            environment="staging",
            gitops_root=tmp_path,
        )

        assert result == "in_sync"

    finally:
        release.set()
        process.join(timeout=5)

        if process.is_alive():
            process.terminate()
            process.join(timeout=5)

    assert process.exitcode == 0


def test_reconciliation_blocks_until_lock_is_released(
    db_session,
    tmp_path,
):
    application_id = prepare_reconciliation_data(
        db_session, tmp_path
    )

    context = multiprocessing.get_context("spawn")
    locked = context.Event()
    release = context.Event()

    process = context.Process(
        target=hold_gitops_lock,
        args=(str(tmp_path), locked, release),
    )

    process.start()

    try:
        assert locked.wait(timeout=5), "Worker did not acquire lock"

        # Try to acquire the same lock without blocking.
        # It must be unavailable while the worker holds it.
        import fcntl

        lock_path = (
            tmp_path
            / ".locks"
            / "staging--reconciliation-api.lock"
        )

        with lock_path.open("a+") as lock_file:
            try:
                fcntl.flock(
                    lock_file.fileno(),
                    fcntl.LOCK_EX | fcntl.LOCK_NB,
                )
            except BlockingIOError:
                lock_is_held = True
            else:
                lock_is_held = False
                fcntl.flock(
                    lock_file.fileno(),
                    fcntl.LOCK_UN,
                )

        assert lock_is_held, "Expected GitOps lock to be held"

        release.set()

        result = check_deployment_drift(
            db=db_session,
            application_id=application_id,
            environment="staging",
            gitops_root=tmp_path,
        )

        assert result == "in_sync"

    finally:
        release.set()
        process.join(timeout=5)

        if process.is_alive():
            process.terminate()
            process.join(timeout=5)

    assert process.exitcode == 0
