"""CLI for reconciling pending deployment namespace bootstraps."""

import argparse
import json
import os
import sys

from kubernetes import client, config

from afterpush_api.database import SessionLocal
from afterpush_api.services.namespace_bootstrap_worker import (
    reconcile_pending_namespace_bootstraps,
)
from afterpush_api.services.deployment_selection import (
    get_pending_deployment_ids,
)


def create_bootstrap_core_api():
    """Create a Kubernetes CoreV1Api using isolated configuration."""

    configuration = client.Configuration()

    if os.getenv("KUBERNETES_SERVICE_HOST"):
        config.load_incluster_config(
            client_configuration=configuration,
        )
    else:
        config.load_kube_config(
            client_configuration=configuration,
        )

    return client.CoreV1Api(
        client.ApiClient(configuration=configuration)
    )


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="Reconcile AfterPush namespace bootstraps."
    )

    parser.add_argument(
        "--limit",
        type=int,
        default=20,
    )

    parser.add_argument(
        "--execute",
        action="store_true",
        help="Allow bootstrap GitOps publication.",
    )

    args = parser.parse_args(argv)

    if args.limit < 1:
        parser.error("--limit must be greater than zero")

    if not args.execute:
        with SessionLocal() as db:
            deployment_ids = get_pending_deployment_ids(
                db=db,
                limit=args.limit,
            )

        print(
            json.dumps(
                {
                    "mode": "dry-run",
                    "pending_deployments": len(deployment_ids),
                    "publication_enabled": False,
                },
                sort_keys=True,
            )
        )

        return 0

    repository_url = os.getenv(
        "AFTERPUSH_GITOPS_REPOSITORY_URL", ""
    ).strip()

    if not repository_url:
        print(
            "ERROR: AFTERPUSH_GITOPS_REPOSITORY_URL is required.",
            file=sys.stderr,
        )
        return 2

    try:
        core_api = create_bootstrap_core_api()

        with SessionLocal() as db:
            results = reconcile_pending_namespace_bootstraps(
                db=db,
                repository_url=repository_url,
                core_api=core_api,
                limit=args.limit,
            )

    except Exception as exc:
        print(
            f"ERROR: Bootstrap reconciliation failed: {exc}",
            file=sys.stderr,
        )
        return 1

    print(json.dumps(results, sort_keys=True))

    return 1 if results["errors"] else 0


if __name__ == "__main__":
    sys.exit(main())
