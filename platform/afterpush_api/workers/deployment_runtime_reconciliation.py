import argparse
import json
import os
import sys

from afterpush_api.database import SessionLocal
from afterpush_api.services.deployment_runtime_reconciliation import (
    reconcile_deployment_runtimes_managed,
)
from afterpush_api.services.kubernetes_client_factory import (
    create_kubernetes_reader,
)
from afterpush_api.services.kubernetes_runtime_observer import (
    KubernetesRuntimeObserver,
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Reconcile AfterPush deployment runtime states."
    )
    parser.add_argument("--limit", type=int, default=20)
    parser.add_argument("--kubeconfig-context", default=None)
    parser.add_argument(
        "--in-cluster",
        action="store_true",
        help="Use Kubernetes ServiceAccount credentials inside a Pod.",
    )
    args = parser.parse_args()

    if args.limit < 1:
        parser.error("--limit must be greater than zero")

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
        reader = create_kubernetes_reader(
            in_cluster=args.in_cluster,
            kubeconfig_context=args.kubeconfig_context,
        )
        observer = KubernetesRuntimeObserver(reader)

        results = reconcile_deployment_runtimes_managed(
                SessionLocal,
                observer=observer,
                repository_url=repository_url,
                limit=args.limit,
            )

    except Exception as exc:
        print(f"ERROR: Runtime reconciliation failed: {exc}", file=sys.stderr)
        return 1

    print(json.dumps(results, sort_keys=True))
    return 1 if results["errors"] else 0


if __name__ == "__main__":
    sys.exit(main())
