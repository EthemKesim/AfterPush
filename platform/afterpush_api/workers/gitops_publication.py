import argparse
import json
import os
import sys

from afterpush_api.database import SessionLocal
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

    try:
        with SessionLocal() as db:
            results = process_pending_publications(
                db=db,
                gitops_repository_url=repository_url,
                limit=args.limit,
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
