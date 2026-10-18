from pathlib import Path

import yaml


PROJECT_ROOT = Path(__file__).resolve().parents[3]
EKS_VALUES_FILES = (
    PROJECT_ROOT / "gitops/apps/afterpush-api/values.yaml",
    PROJECT_ROOT / "gitops/apps/afterpush-api/values-eks.yaml",
)


def test_eks_values_keep_the_unauthenticated_api_internal():
    """The final EKS profile must not expose the management API publicly."""
    for values_file in EKS_VALUES_FILES:
        values = yaml.safe_load(values_file.read_text(encoding="utf-8"))

        assert values["ingress"]["enabled"] is True
        assert values["ingress"]["className"] == "alb"
        assert values["ingress"]["annotations"][
            "alb.ingress.kubernetes.io/scheme"
        ] == "internal"
        assert values.get("networkPolicy", {}).get("enabled", False) is False
