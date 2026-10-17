
import multiprocessing

import yaml

from afterpush_api.services.sync import (
    sync_gitops_application,
)


def sync_worker(
    gitops_root,
    image_tag,
    start_event,
    result_queue,
):
    """
    Wait for the start signal, then synchronize
    the same GitOps application.
    """
    try:
        if not start_event.wait(timeout=10):
            raise TimeoutError("Start signal not received")

        result = sync_gitops_application(
            gitops_root=gitops_root,
            application_name="payment-service",
            environment="staging",
            image_repository="nginx",
            image_tag=image_tag,
            port=3000,
            replicas=2,
        )

        result_queue.put(("success", str(result)))

    except Exception as error:
        result_queue.put(("error", str(error)))


def test_concurrent_gitops_sync(tmp_path):
    context = multiprocessing.get_context("spawn")

    start_event = context.Event()
    result_queue = context.Queue()

    first = context.Process(
        target=sync_worker,
        args=(
            tmp_path,
            "v2.0.0",
            start_event,
            result_queue,
        ),
    )

    second = context.Process(
        target=sync_worker,
        args=(
            tmp_path,
            "v3.0.0",
            start_event,
            result_queue,
        ),
    )

    processes = (first, second)

    try:
        for process in processes:
            process.start()

        start_event.set()

        results = [
            result_queue.get(timeout=15)
            for _ in processes
        ]

        assert all(
            status == "success"
            for status, _ in results
        ), results

        values_path = (
            tmp_path
            / "apps"
            / "staging"
            / "payment-service"
            / "values.yaml"
        )

        assert values_path.is_file()

        with values_path.open(
            "r",
            encoding="utf-8",
        ) as file:
            values = yaml.safe_load(file)

        assert values["image"]["repository"] == "nginx"

        assert values["image"]["tag"] in {
            "v2.0.0",
            "v3.0.0",
        }

        assert values["application"]["name"] == "payment-service"
        assert values["replicaCount"] == 2

    finally:
        start_event.set()

        for process in processes:
            if process.pid is not None:
                process.join(timeout=5)

                if process.is_alive():
                    process.terminate()
                    process.join(timeout=5)

        result_queue.close()
        result_queue.join_thread()
