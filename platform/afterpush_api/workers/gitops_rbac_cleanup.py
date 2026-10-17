import argparse
import json
import logging
import os
import sys

from afterpush_api.database import SessionLocal
from afterpush_api.services.gitops_rbac_cleanup_dry_run import (
    plan_rbac_cleanup,
)
from afterpush_api.services.gitops_workspace import (
    isolated_gitops_workspace,
)


logger = logging.getLogger(__name__)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="Inspect orphaned AfterPush RBAC manifests."
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=100,
    )
    args = parser.parse_args(argv)

    if args.batch_size < 1:
        parser.error("--batch-size must be greater than zero")

    repository_url = os.getenv(
        "AFTERPUSH_GITOPS_REPOSITORY_URL"
    )

    if not repository_url:
        print(
            "ERROR: AFTERPUSH_GITOPS_REPOSITORY_URL is required",
            file=sys.stderr,
        )
        return 2

    try:
        with isolated_gitops_workspace(repository_url) as workspace:
            with SessionLocal() as db:
                result = plan_rbac_cleanup(
                    db=db,
                    repository_root=workspace,
                    batch_size=args.batch_size,
                )

        print(
            json.dumps(
                {
                    "mode": "dry-run",
                    "valid_target_count": result.valid_target_count,
                    "orphaned_count": len(
                        result.orphaned_candidates
                    ),
                    "orphaned_directories": [
                        str(candidate.relative_directory)
                        for candidate in result.orphaned_candidates
                    ],
                },
                indent=2,
            )
        )
        return 0

    except Exception:
        logger.exception("RBAC cleanup dry-run failed")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
