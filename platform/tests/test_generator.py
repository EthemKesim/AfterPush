import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
PLATFORM_ROOT = PROJECT_ROOT / "platform"

if str(PLATFORM_ROOT) not in sys.path:
    sys.path.insert(0, str(PLATFORM_ROOT))

from afterpush_engine.generation import generate_helm_values  # noqa: E402


def get_config(profile="local"):
    return {
        "apiVersion": "afterpush.dev/v1",
        "kind": "Application",
        "metadata": {
            "name": "demo-api",
        },
        "spec": {
            "profile": profile,
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
    values = generate_helm_values(get_config())

    assert values["image"]["repository"] == "afterpush-api"
    assert values["image"]["tag"] == "metrics"


def test_generator_maps_application_port():
    values = generate_helm_values(get_config())

    assert values["service"]["targetPort"] == 3000


def test_generator_maps_health_path_to_both_probes():
    values = generate_helm_values(get_config())

    assert values["probes"]["readiness"]["path"] == "/health"
    assert values["probes"]["liveness"]["path"] == "/health"


def test_generator_maps_scaling_configuration():
    values = generate_helm_values(get_config())

    assert values["autoscaling"]["enabled"] is True
    assert values["autoscaling"]["minReplicas"] == 2
    assert values["autoscaling"]["maxReplicas"] == 5
    assert (
        values["autoscaling"]["targetCPUUtilizationPercentage"]
        == 50
    )


def test_generator_applies_platform_defaults():
    values = generate_helm_values(get_config())

    assert values["service"]["type"] == "ClusterIP"
    assert values["image"]["pullPolicy"] == "Never"
    assert values["config"]["appEnv"] == "local"
    assert values["config"]["logLevel"] == "debug"
    assert values["ingress"]["className"] == "nginx"

    assert values["resources"]["requests"]["cpu"] == "100m"
    assert values["resources"]["requests"]["memory"] == "128Mi"

    assert values["resources"]["limits"]["cpu"] == "500m"
    assert values["resources"]["limits"]["memory"] == "256Mi"


def test_generator_applies_eks_platform_defaults():
    values = generate_helm_values(get_config(profile="eks"))

    assert values["image"]["pullPolicy"] == "IfNotPresent"
    assert values["config"]["appEnv"] == "eks"
    assert values["config"]["logLevel"] == "info"
    assert values["ingress"]["className"] == "alb"


def test_generator_defaults_to_local_profile():
    config = get_config()
    del config["spec"]["profile"]

    values = generate_helm_values(config)

    assert values["image"]["pullPolicy"] == "Never"
    assert values["config"]["appEnv"] == "local"
    assert values["config"]["logLevel"] == "debug"
    assert values["ingress"]["className"] == "nginx"


def test_generator_maps_monitoring():
    values = generate_helm_values(get_config())

    assert values["monitoring"]["enabled"] is True


def test_generator_maps_application_name():
    values = generate_helm_values(get_config())

    assert values["application"]["name"] == "demo-api"