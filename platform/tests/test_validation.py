import importlib.util
from pathlib import Path

from jsonschema import Draft202012Validator


PROJECT_ROOT = Path(__file__).resolve().parents[2]
VALIDATOR_PATH = PROJECT_ROOT / "platform/cli/validate.py"
SCHEMA_PATH = PROJECT_ROOT / "platform/schema/afterpush.schema.json"
EXAMPLE_PATH = PROJECT_ROOT / "platform/examples/afterpush.yaml"


def load_validator_module():
    spec = importlib.util.spec_from_file_location(
        "afterpush_validator",
        VALIDATOR_PATH,
    )

    if spec is None or spec.loader is None:
        raise RuntimeError("Could not load AfterPush validator module.")

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    return module


validator_module = load_validator_module()


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
    return validator_module.load_json(SCHEMA_PATH)


def get_schema_errors(config):
    validator = Draft202012Validator(get_schema())
    return list(validator.iter_errors(config))


def test_example_config_is_valid():
    config = validator_module.load_yaml(EXAMPLE_PATH)

    assert get_schema_errors(config) == []
    assert validator_module.validate_business_rules(config) == []


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

    errors = validator_module.validate_business_rules(config)

    assert (
        "spec.scaling.minReplicas cannot be greater than "
        "spec.scaling.maxReplicas."
    ) in errors


def test_ingress_requires_host_when_enabled():
    config = get_valid_config()

    del config["spec"]["ingress"]["host"]

    errors = validator_module.validate_business_rules(config)

    assert (
        "spec.ingress.host is required when ingress is enabled."
    ) in errors