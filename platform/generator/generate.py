import sys
from pathlib import Path

import yaml


def load_yaml(path: Path):
    with path.open("r", encoding="utf-8") as file:
        return yaml.safe_load(file)


def generate_helm_values(config: dict) -> dict:
    spec = config["spec"]

    ingress = spec.get("ingress", {"enabled": False})
    scaling = spec.get("scaling", {"enabled": False})
    monitoring = spec.get("monitoring", {"enabled": False})

    values = {
        "application": {
            "name": config["metadata"]["name"],
        },
        "image": {
            "repository": spec["image"]["repository"],
            "tag": spec["image"]["tag"],
            "pullPolicy": "Never",
        },

        "service": {
            "type": "ClusterIP",
            "port": 80,
            "targetPort": spec["port"],
        },

        "config": {
            "appEnv": "local",
            "logLevel": "debug",
        },

        "ingress": {
            "enabled": ingress.get("enabled", False),
            "className": "nginx",
            "host": ingress.get("host", ""),
            "path": "/",
            "pathType": "Prefix",
        },

        "autoscaling": {
            "enabled": scaling.get("enabled", False),
            "minReplicas": scaling.get("minReplicas", 2),
            "maxReplicas": scaling.get("maxReplicas", 5),
            "targetCPUUtilizationPercentage": scaling.get(
                "targetCPUUtilization",
                50,
            ),
        },

        "resources": {
            "requests": {
                "cpu": "100m",
                "memory": "128Mi",
            },
            "limits": {
                "cpu": "500m",
                "memory": "256Mi",
            },
        },

        "probes": {
            "readiness": {
                "path": spec["health"]["path"],
                "initialDelaySeconds": 2,
                "periodSeconds": 5,
            },
            "liveness": {
                "path": spec["health"]["path"],
                "initialDelaySeconds": 5,
                "periodSeconds": 10,
            },
        },

        "monitoring": {
            "enabled": monitoring.get("enabled", False),
        },
    }

    return values


def main():
    project_root = Path(__file__).resolve().parents[2]

    config_path = (
        Path(sys.argv[1])
        if len(sys.argv) > 1
        else project_root / "platform/examples/afterpush.yaml"
    )

    config = load_yaml(config_path)
    values = generate_helm_values(config)

    print(
        yaml.safe_dump(
            values,
            sort_keys=False,
        )
    )


if __name__ == "__main__":
    main()