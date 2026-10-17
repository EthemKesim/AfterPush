"""CLI for inspecting deployment prerequisites."""

import argparse
import json
import os
import sys


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Inspect AfterPush deployment prerequisites."
    )

    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true")
    mode.add_argument("--execute", action="store_true")

    parser.add_argument("--limit", type=int, default=20)
    parser.add_argument("--in-cluster", action="store_true")
    parser.add_argument("--kubeconfig-context", default=None)

    args = parser.parse_args()

    if args.limit < 1:
        parser.error("--limit must be greater than zero")

    if args.in_cluster and args.kubeconfig_context is not None:
        parser.error(
            "--in-cluster cannot be combined with --kubeconfig-context"
        )

    if args.execute:
        print(
            "ERROR: --execute is disabled pending production safety review.",
            file=sys.stderr,
        )
        return 2

    database_url = os.getenv("DATABASE_URL", "").strip()

    if not database_url:
        print(
            "ERROR: DATABASE_URL must be explicitly configured.",
            file=sys.stderr,
        )
        return 2

    if database_url.rsplit("/", 1)[-1].split("?", 1)[0] != "afterpush_test":
        print(
            "ERROR: Initial dry-run is restricted to afterpush_test.",
            file=sys.stderr,
        )
        return 2

    try:
        from sqlalchemy import create_engine
        from sqlalchemy.orm import Session

        from afterpush_api.services.prerequisites_kubernetes_client import (
            create_prerequisites_clients,
        )
        from afterpush_api.services.deployment_prerequisites_dry_run import (
            inspect_pending_prerequisites,
        )

        core_api, rbac_api = create_prerequisites_clients(
            in_cluster=args.in_cluster,
            kubeconfig_context=args.kubeconfig_context,
        )

        engine = create_engine(database_url, pool_pre_ping=True)

        try:
            with Session(engine) as db:
                results = inspect_pending_prerequisites(
                    db=db,
                    core_api=core_api,
                    rbac_api=rbac_api,
                    limit=args.limit,
                )
        finally:
            engine.dispose()

    except Exception as exc:
        print(
            f"ERROR: Prerequisites inspection failed: {exc}",
            file=sys.stderr,
        )
        return 1

    print(json.dumps(results, sort_keys=True))

    return 1 if results["errors"] else 0


if __name__ == "__main__":
    sys.exit(main())
