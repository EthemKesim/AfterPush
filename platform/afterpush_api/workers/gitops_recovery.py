import argparse
import json
import os
import sys

from afterpush_api.database import SessionLocal
from afterpush_api.services.deployment_recovery import (
    get_stale_publications,
    recover_published_deployment,
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Recover published AfterPush GitOps deployments."
    )
    parser.add_argument(
        "--timeout-minutes",
        type=int,
        default=15,
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=100,
    )

    args = parser.parse_args()

    if args.timeout_minutes < 1:
        parser.error("--timeout-minutes must be at least 1")

    if args.limit < 1:
        parser.error("--limit must be at least 1")

    repository_url = os.getenv(
        "AFTERPUSH_GITOPS_REPOSITORY_URL", ""
    ).strip()

    if not repository_url:
        print(
            "ERROR: AFTERPUSH_GITOPS_REPOSITORY_URL is required.",
            file=sys.stderr,
        )
        return 2

    results = {
        "recovered": 0,
        "not_published": 0,
        "not_eligible": 0,
        "not_found": 0,
        "claim_changed": 0,
        "errors": 0,
    }

    try:
        with SessionLocal() as db:
            stale_ids = [
                deployment.id
                for deployment in get_stale_publications(
                    db,
                    timeout_minutes=args.timeout_minutes,
                    limit=args.limit,
                )
            ]

            db.rollback()

            for deployment_id in stale_ids:
                try:
                    result = recover_published_deployment(
                        db=db,
                        deployment_id=deployment_id,
                        gitops_repository_url=repository_url,
                        timeout_minutes=args.timeout_minutes,
                    )

                    if result == "superseded":
                        results["not_published"] += 1
                    else:
                        results[result] += 1
                    db.rollback()

                except Exception as exc:
                    db.rollback()
                    results["errors"] += 1
                    print(
                        f"Recovery failed for {deployment_id}: {exc}",
                        file=sys.stderr,
                    )

    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    print(json.dumps(results, sort_keys=True))

    return 1 if results["errors"] else 0


if __name__ == "__main__":
    sys.exit(main())
