import sys
from pathlib import Path

from jsonschema import Draft202012Validator


PROJECT_ROOT = Path(__file__).resolve().parents[2]
PLATFORM_ROOT = PROJECT_ROOT / "platform"

if str(PLATFORM_ROOT) not in sys.path:
    sys.path.insert(0, str(PLATFORM_ROOT))

from afterpush_engine.validation import (  # noqa: E402
    load_schema,
    load_yaml,
    validate_business_rules,
    validate_config,
)


EXAMPLE_PATH = PROJECT_ROOT / "platform/examples/afterpush.yaml"


def get_valid_config():
    return {
        "apiVersion": "afterpush.dev/v1",
        "kind": "Application",
        "metadata": {
            "name": "demo-api",
        },
        "spec": {
            "image": {
                "repository": "afterpush-api",
                "tag": "metrics",
            },
            "port": 3000,
            "health": {
                "path": "/health",
            },
            "ingress": {
                "enabled": True,
                "host": "afterpush.local",
            },
            "scaling": {
                "enabled": True,
                "minReplicas": 2,
                "maxReplicas": 5,
                "targetCPUUtilization": 50,
            },
            "monitoring": {
                "enabled": True,
            },
        },
    }


def get_schema():
    return load_schema()


def get_schema_errors(config):
    validator = Draft202012Validator(get_schema())
    return list(validator.iter_errors(config))


def test_example_config_is_valid():
    config = load_yaml(EXAMPLE_PATH)

    errors = validate_config(config, get_schema())

    assert errors == []


def test_invalid_port_is_rejected():
    config = get_valid_config()
    config["spec"]["port"] = -3000

    errors = get_schema_errors(config)

    assert len(errors) > 0


def test_invalid_monitoring_type_is_rejected():
    config = get_valid_config()
    config["spec"]["monitoring"]["enabled"] = "yes"

    errors = get_schema_errors(config)

    assert len(errors) > 0


def test_min_replicas_cannot_exceed_max_replicas():
    config = get_valid_config()

    config["spec"]["scaling"]["minReplicas"] = 10
    config["spec"]["scaling"]["maxReplicas"] = 2

    errors = validate_business_rules(config)

    assert (
        "spec.scaling.minReplicas cannot be greater than "
        "spec.scaling.maxReplicas."
    ) in errors


def test_ingress_requires_host_when_enabled():
    config = get_valid_config()

    del config["spec"]["ingress"]["host"]

    errors = validate_business_rules(config)

    assert (
        "spec.ingress.host is required when ingress is enabled."
    ) in errors


def test_application_name_rejects_path_traversal():
    config = load_yaml(EXAMPLE_PATH)
    schema = load_schema()

    config["metadata"]["name"] = "../../outside"

    errors = validate_config(config, schema)

    assert errors
    assert any(
        "metadata.name" in error
        for error in errors
    )