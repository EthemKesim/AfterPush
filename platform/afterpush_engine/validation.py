import json
from pathlib import Path

import yaml
from jsonschema import Draft202012Validator

from importlib.resources import files


def load_yaml(path: Path):
    with path.open("r", encoding="utf-8") as file:
        return yaml.safe_load(file)

def load_schema() -> dict:
    schema_resource = (
        files("afterpush_engine")
        .joinpath("schema")
        .joinpath("afterpush.schema.json")
    )

    with schema_resource.open("r", encoding="utf-8") as file:
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


def validate_config(config: dict, schema: dict) -> list[str]:
    errors = []

    validator = Draft202012Validator(schema)

    schema_errors = sorted(
        validator.iter_errors(config),
        key=lambda error: list(error.absolute_path),
    )

    for error in schema_errors:
        path = format_path(error)
        errors.append(f"{path}: {error.message}")

    # Business validation only makes sense after the
    # configuration has passed structural schema validation.
    if errors:
        return errors

    errors.extend(validate_business_rules(config))

    return errors