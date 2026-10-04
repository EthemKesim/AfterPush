import importlib.util
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
GENERATOR_PATH = PROJECT_ROOT / "platform/generator/generate.py"


def load_generator_module():
    spec = importlib.util.spec_from_file_location(
        "afterpush_generator",
        GENERATOR_PATH,
    )

    if spec is None or spec.loader is None:
        raise RuntimeError("Could not load AfterPush generator module.")

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    return module


generator_module = load_generator_module()


def get_config():
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


def test_generator_maps_image():
    values = generator_module.generate_helm_values(get_config())

    assert values["image"]["repository"] == "afterpush-api"
    assert values["image"]["tag"] == "metrics"


def test_generator_maps_application_port():
    values = generator_module.generate_helm_values(get_config())

    assert values["service"]["targetPort"] == 3000


def test_generator_maps_health_path_to_both_probes():
    values = generator_module.generate_helm_values(get_config())

    assert values["probes"]["readiness"]["path"] == "/health"
    assert values["probes"]["liveness"]["path"] == "/health"


def test_generator_maps_scaling_configuration():
    values = generator_module.generate_helm_values(get_config())

    assert values["autoscaling"]["enabled"] is True
    assert values["autoscaling"]["minReplicas"] == 2
    assert values["autoscaling"]["maxReplicas"] == 5
    assert (
        values["autoscaling"]["targetCPUUtilizationPercentage"]
        == 50
    )


def test_generator_applies_platform_defaults():
    values = generator_module.generate_helm_values(get_config())

    assert values["service"]["type"] == "ClusterIP"
    assert values["ingress"]["className"] == "nginx"

    assert values["resources"]["requests"]["cpu"] == "100m"
    assert values["resources"]["requests"]["memory"] == "128Mi"

    assert values["resources"]["limits"]["cpu"] == "500m"
    assert values["resources"]["limits"]["memory"] == "256Mi"


def test_generator_maps_monitoring():
    values = generator_module.generate_helm_values(get_config())

    assert values["monitoring"]["enabled"] is True

def test_generator_maps_application_name():
    values = generator_module.generate_helm_values(get_config())

    assert values["application"]["name"] == "demo-api"
