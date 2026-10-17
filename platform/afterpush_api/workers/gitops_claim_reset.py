"""Operator-controlled reset for abandoned GitOps publication claims."""

import argparse
import json
import sys
from uuid import UUID

from afterpush_api.database import SessionLocal
from afterpush_api.services.deployment_claim_reset import (
    reset_stale_publication,
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Reset a stale AfterPush GitOps publication claim."
    )
    parser.add_argument(
        "--deployment-id",
        required=True,
        type=UUID,
        help="Deployment UUID whose claim will be reset.",
    )
    parser.add_argument(
        "--claim-id",
        required=True,
        type=UUID,
        help="The stale publication claim UUID to reset.",
    )
    parser.add_argument(
        "--timeout-minutes",
        type=int,
        default=15,
        help="Minimum claim age before reset is permitted.",
    )
    parser.add_argument(
        "--confirm-worker-stopped",
        action="store_true",
        help="Confirm the worker holding the claim cannot publish to Git.",
    )

    args = parser.parse_args()

    if args.timeout_minutes < 1:
        parser.error("--timeout-minutes must be at least 1")

    if not args.confirm_worker_stopped:
        parser.error(
            "--confirm-worker-stopped is required before a claim can reset"
        )

    try:
        with SessionLocal() as db:
            result = reset_stale_publication(
                db=db,
                deployment_id=args.deployment_id,
                claim_id=args.claim_id,
                timeout_minutes=args.timeout_minutes,
                worker_confirmed_stopped=True,
            )

            if result == "reset":
                db.commit()
            else:
                db.rollback()

    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    print(
        json.dumps(
            {
                "deployment_id": str(args.deployment_id),
                "result": result,
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
