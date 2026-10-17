import argparse
import json
import os
import sys

from afterpush_api.database import SessionLocal
from afterpush_api.services.gitops_rbac_reconciler import (
    reconcile_published_rbac,
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Reconcile AfterPush observer RBAC "
            "for published deployments."
        )
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=20,
        help="Number of RBAC targets fetched per database page.",
    )
    args = parser.parse_args()

    if args.batch_size < 1:
        parser.error("--batch-size must be greater than zero")

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
        with SessionLocal() as db:
            result = reconcile_published_rbac(
                db=db,
                repository_url=repository_url,
                batch_size=args.batch_size,
            )
    except Exception as exc:
        print(
            f"ERROR: RBAC reconciliation failed: {exc}",
            file=sys.stderr,
        )
        return 1

    output = {
        "processed": result.processed,
        "succeeded": result.succeeded,
        "failed": result.failed,
        "failed_targets": [
            {
                "project_id": str(target.project_id),
                "application_name": target.application_name,
                "environment": target.environment,
            }
            for target in result.failed_targets
        ],
    }

    print(json.dumps(output, sort_keys=True))

    return 1 if result.failed else 0


if __name__ == "__main__":
    sys.exit(main())
