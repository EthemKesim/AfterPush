def generate_helm_values(config: dict) -> dict:
    spec = config["spec"]

    profile = spec.get("profile", "local")

    ingress = spec.get("ingress", {"enabled": False})
    scaling = spec.get("scaling", {"enabled": False})
    monitoring = spec.get("monitoring", {"enabled": False})

    profiles = {
        "local": {
            "pullPolicy": "Never",
            "appEnv": "local",
            "logLevel": "debug",
            "ingressClassName": "nginx",
            "ingressAnnotations": {},
        },
        "eks": {
            "pullPolicy": "IfNotPresent",
            "appEnv": "eks",
            "logLevel": "info",
            "ingressClassName": "alb",
            "ingressAnnotations": {
                "alb.ingress.kubernetes.io/scheme": "internet-facing",
                "alb.ingress.kubernetes.io/target-type": "ip",
                "alb.ingress.kubernetes.io/healthcheck-path": spec["health"]["path"],
            },
        },
    }

    platform_defaults = profiles[profile]

    values = {
        "application": {
            "name": config["metadata"]["name"],
        },

        "image": {
            "repository": spec["image"]["repository"],
            "tag": spec["image"]["tag"],
            "pullPolicy": platform_defaults["pullPolicy"],
        },

        "service": {
            "type": "ClusterIP",
            "port": 80,
            "targetPort": spec["port"],
        },

        "config": {
            "appEnv": platform_defaults["appEnv"],
            "logLevel": platform_defaults["logLevel"],
        },

        "ingress": {
            "enabled": ingress.get("enabled", False),
            "className": platform_defaults["ingressClassName"],
            "annotations": platform_defaults["ingressAnnotations"],
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