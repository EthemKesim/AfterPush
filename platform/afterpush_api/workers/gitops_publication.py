import argparse
import json
import os
import sys

from kubernetes import client, config

from afterpush_api.database import SessionLocal


def create_publication_core_api():
    try:
        if os.getenv("KUBERNETES_SERVICE_HOST"):
            config.load_incluster_config()
        else:
            config.load_kube_config()
    except config.ConfigException:
        # A missing local kubeconfig means the namespace gate cannot be
        # verified yet. Let the publication worker record a deferred attempt
        # instead of turning an expected readiness state into a batch error.
        return None

    return client.CoreV1Api()
from afterpush_api.services.deployment_publication_worker import (
    process_pending_publications,
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Publish pending AfterPush deployments to GitOps."
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=20,
        help="Maximum number of deployments to process.",
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Publish pending deployments to the configured GitOps repository.",
    )
    args = parser.parse_args()

    if args.limit < 1:
        parser.error("--limit must be greater than zero")

    repository_url = os.getenv("AFTERPUSH_GITOPS_REPOSITORY_URL", "").strip()

    if not repository_url:
        print(
            "ERROR: AFTERPUSH_GITOPS_REPOSITORY_URL is required.",
            file=sys.stderr,
        )
        return 2

    if not args.execute:
        print(
            "ERROR: --execute is required before publishing to GitOps.",
            file=sys.stderr,
        )
        return 2

    try:
        core_api = create_publication_core_api()
        rbac_api = client.RbacAuthorizationV1Api()

        with SessionLocal() as db:
            results = process_pending_publications(
                db=db,
                gitops_repository_url=repository_url,
                limit=args.limit,
                core_api=core_api,
                rbac_api=rbac_api,
            )

    except Exception as exc:
        print(
            f"ERROR: Publication batch failed: {exc}",
            file=sys.stderr,
        )
        return 1

    print(json.dumps(results, sort_keys=True))

    return 1 if results["errors"] else 0


if __name__ == "__main__":
    sys.exit(main())
