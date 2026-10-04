import json
import sys
from pathlib import Path

import yaml
from jsonschema import Draft202012Validator


def load_yaml(path: Path):
    with path.open("r", encoding="utf-8") as file:
        return yaml.safe_load(file)


def load_json(path: Path):
    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


def format_path(error) -> str:
    if not error.absolute_path:
        return "configuration"

    return ".".join(str(part) for part in error.absolute_path)


def validate_business_rules(config: dict) -> list[str]:
    errors = []

    spec = config.get("spec", {})

    # Scaling rules
    scaling = spec.get("scaling", {})

    if scaling.get("enabled") is True:
        min_replicas = scaling.get("minReplicas")
        max_replicas = scaling.get("maxReplicas")

        if min_replicas is None:
            errors.append(
                "spec.scaling.minReplicas is required when scaling is enabled."
            )

        if max_replicas is None:
            errors.append(
                "spec.scaling.maxReplicas is required when scaling is enabled."
            )

        if (
            min_replicas is not None
            and max_replicas is not None
            and min_replicas > max_replicas
        ):
            errors.append(
                "spec.scaling.minReplicas cannot be greater than "
                "spec.scaling.maxReplicas."
            )

    # Ingress rules
    ingress = spec.get("ingress", {})

    if ingress.get("enabled") is True and not ingress.get("host"):
        errors.append(
            "spec.ingress.host is required when ingress is enabled."
        )

    return errors


def main():
    project_root = Path(__file__).resolve().parents[2]

    config_path = (
        Path(sys.argv[1])
        if len(sys.argv) > 1
        else project_root / "platform/examples/afterpush.yaml"
    )

    schema_path = project_root / "platform/schema/afterpush.schema.json"

    try:
        config = load_yaml(config_path)
        schema = load_json(schema_path)
    except FileNotFoundError as error:
        print(f"✗ File not found: {error.filename}")
        sys.exit(1)
    except yaml.YAMLError as error:
        print(f"✗ Invalid YAML: {error}")
        sys.exit(1)
    except json.JSONDecodeError as error:
        print(f"✗ Invalid schema JSON: {error}")
        sys.exit(1)

    # Layer 1: Schema validation
    validator = Draft202012Validator(schema)

    schema_errors = sorted(
        validator.iter_errors(config),
        key=lambda error: list(error.absolute_path),
    )

    if schema_errors:
        print("✗ AfterPush configuration failed schema validation:\n")

        for error in schema_errors:
            path = format_path(error)
            print(f"  - {path}: {error.message}")

        sys.exit(1)

    # Layer 2: Business validation
    business_errors = validate_business_rules(config)

    if business_errors:
        print("✗ AfterPush configuration failed business validation:\n")

        for error in business_errors:
            print(f"  - {error}")

        sys.exit(1)

    print("✓ AfterPush configuration is valid.")


if __name__ == "__main__":
    main()