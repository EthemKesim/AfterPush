from pathlib import Path

from afterpush_engine.generation import generate_helm_values
from afterpush_engine.validation import (
    load_schema,
    load_yaml,
    validate_config,
)


class ConfigurationValidationError(Exception):
    def __init__(self, errors: list[str]):
        self.errors = errors

        super().__init__(
            "AfterPush configuration validation failed."
        )


def build_helm_values(config_path: Path) -> dict:
    config = load_yaml(config_path)
    schema = load_schema()

    errors = validate_config(config, schema)

    if errors:
        raise ConfigurationValidationError(errors)

    return generate_helm_values(config)