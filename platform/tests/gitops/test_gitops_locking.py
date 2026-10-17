
import multiprocessing
import time

import pytest

from afterpush_api.services.gitops import InvalidGitOpsPathError
from afterpush_api.services.locking import gitops_application_lock


def lock_worker(
    gitops_root,
    application_name,
    environment,
    acquired_event,
    release_event,
):
    with gitops_application_lock(
        gitops_root,
        application_name,
        environment,
    ):
        acquired_event.set()
        release_event.wait(timeout=10)


def test_lock_creates_lock_file(tmp_path):
    with gitops_application_lock(
        tmp_path,
        "payment-service",
        "staging",
    ):
        lock_path = (
            tmp_path
            / ".locks"
            / "staging--payment-service.lock"
        )

        assert lock_path.is_file()


def test_lock_is_released_after_context(tmp_path):
    with gitops_application_lock(
        tmp_path,
        "payment-service",
        "staging",
    ):
        pass

    with gitops_application_lock(
        tmp_path,
        "payment-service",
        "staging",
    ):
        pass


def test_lock_rejects_invalid_application_name(tmp_path):
    with pytest.raises(InvalidGitOpsPathError):
        with gitops_application_lock(
            tmp_path,
            "../outside",
            "staging",
        ):
            pass


def test_lock_rejects_symlinked_lock_directory(tmp_path):
    outside = tmp_path / "outside"
    outside.mkdir()

    root = tmp_path / "gitops"
    root.mkdir()

    (root / ".locks").symlink_to(
        outside,
        target_is_directory=True,
    )

    with pytest.raises(InvalidGitOpsPathError):
        with gitops_application_lock(
            root,
            "payment-service",
            "staging",
        ):
            pass


def test_lock_serializes_two_processes(tmp_path):
    context = multiprocessing.get_context("spawn")

    first_acquired = context.Event()
    first_release = context.Event()
    second_acquired = context.Event()
    second_release = context.Event()

    first = context.Process(
        target=lock_worker,
        args=(
            tmp_path,
            "payment-service",
            "staging",
            first_acquired,
            first_release,
        ),
    )

    second = context.Process(
        target=lock_worker,
        args=(
            tmp_path,
            "payment-service",
            "staging",
            second_acquired,
            second_release,
        ),
    )

    try:
        first.start()
        assert first_acquired.wait(timeout=10)

        second.start()

        time.sleep(0.3)

        assert not second_acquired.is_set()

        first_release.set()

        assert second_acquired.wait(timeout=10)

    finally:
        first_release.set()
        second_release.set()

        for process in (first, second):
            if process.pid is not None:
                process.join(timeout=5)

                if process.is_alive():
                    process.terminate()
                    process.join(timeout=5)
