import argparse
import json
import sys
from pathlib import Path

import yaml

from afterpush_engine.deployment import (
    find_gitops_root,
    prepare_deployment,
)

from afterpush_engine.pipeline import (
    ConfigurationValidationError,
    build_helm_values,
)
from afterpush_engine.validation import (
    load_schema,
    load_yaml,
    validate_config,
)

def create_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="afterpush",
        description="AfterPush self-service application platform.",
    )

    subparsers = parser.add_subparsers(
        dest="command",
        required=True,
    )

    validate_parser = subparsers.add_parser(
        "validate",
        help="Validate an AfterPush application configuration.",
    )
    validate_parser.add_argument(
        "config",
        type=Path,
        help="Path to the afterpush.yaml configuration file.",
    )

    render_parser = subparsers.add_parser(
        "render",
        help="Validate the configuration and generate Helm values.",
    )
    render_parser.add_argument(
        "config",
        type=Path,
        help="Path to the afterpush.yaml configuration file.",
    )

    deploy_parser = subparsers.add_parser(
        "deploy",
        help="Prepare GitOps deployment values for an application.",
    )
    deploy_parser.add_argument(
        "config",
        type=Path,
        help="Path to the afterpush.yaml configuration file.",
    )

    deploy_parser.add_argument(
        "--gitops-root",
        type=Path,
        default=None,
        help=(
            "GitOps applications directory. "
            "Automatically discovered when omitted."
        ),
    )

    return parser


def validate_command(config_path: Path) -> int:
    try:
        config = load_yaml(config_path)
        schema = load_schema()

    except FileNotFoundError as error:
        print(f"✗ File not found: {error.filename}", file=sys.stderr)
        return 1
    except yaml.YAMLError as error:
        print(f"✗ Invalid YAML: {error}", file=sys.stderr)
        return 1
    except json.JSONDecodeError as error:
        print(f"✗ Invalid schema JSON: {error}", file=sys.stderr)
        return 1

    errors = validate_config(config, schema)

    if errors:
        print("✗ AfterPush configuration is invalid:\n", file=sys.stderr)

        for error in errors:
            print(f"  - {error}", file=sys.stderr)

        return 1

    print("✓ AfterPush configuration is valid.")
    return 0


def render_command(config_path: Path) -> int:
    try:
        values = build_helm_values(
            config_path=config_path,
        )
    except FileNotFoundError as error:
        print(f"✗ File not found: {error.filename}", file=sys.stderr)
        return 1
    except yaml.YAMLError as error:
        print(f"✗ Invalid YAML: {error}", file=sys.stderr)
        return 1
    except json.JSONDecodeError as error:
        print(f"✗ Invalid schema JSON: {error}", file=sys.stderr)
        return 1
    except ConfigurationValidationError as error:
        print("✗ AfterPush configuration is invalid:\n", file=sys.stderr)

        for validation_error in error.errors:
            print(f"  - {validation_error}", file=sys.stderr)

        return 1

    sys.stdout.write(
        yaml.safe_dump(
            values,
            sort_keys=False,
        )
    )

    return 0

def deploy_command(
    config_path: Path,
    gitops_root: Path | None,
) -> int:
    try:
        resolved_gitops_root = (
            gitops_root
            if gitops_root is not None
            else find_gitops_root(Path.cwd())
        )

        values_path = prepare_deployment(
            config_path=config_path,
            gitops_root=resolved_gitops_root,
        )

    except FileExistsError as error:
        print(f"✗ {error}", file=sys.stderr)
        return 1
    except FileNotFoundError as error:
        print(f"✗ File not found: {error.filename}", file=sys.stderr)
        return 1
    except yaml.YAMLError as error:
        print(f"✗ Invalid YAML: {error}", file=sys.stderr)
        return 1
    except json.JSONDecodeError as error:
        print(f"✗ Invalid schema JSON: {error}", file=sys.stderr)
        return 1
    except ConfigurationValidationError as error:
        print("✗ AfterPush configuration is invalid:\n", file=sys.stderr)

        for validation_error in error.errors:
            print(f"  - {validation_error}", file=sys.stderr)

        return 1

    print(f"✓ GitOps deployment prepared: {values_path}")


    return 0




def main() -> int:
    parser = create_parser()
    args = parser.parse_args()

    if args.command == "validate":
        return validate_command(args.config)

    if args.command == "render":
        return render_command(args.config)

    if args.command == "deploy":
        return deploy_command(
            args.config,
            args.gitops_root,
        )

    parser.error(f"Unknown command: {args.command}")
    return 2


if __name__ == "__main__":
    sys.exit(main())