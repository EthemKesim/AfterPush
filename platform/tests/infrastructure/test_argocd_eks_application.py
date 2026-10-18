from pathlib import Path

import yaml


PROJECT_ROOT = Path(__file__).resolve().parents[3]
EKS_APPLICATION = PROJECT_ROOT / "argocd/eks/afterpush-api.yaml"
REPOSITORY = "https://github.com/EthemKesim/AfterPush.git"


def test_eks_application_tracks_main_gitops_sources():
    """Keep the standalone EKS entry manifest on the release branch."""
    application = yaml.safe_load(EKS_APPLICATION.read_text(encoding="utf-8"))

    assert application["kind"] == "Application"
    assert application["metadata"]["name"] == "afterpush-api-eks"

    chart_source, values_source = application["spec"]["sources"]

    assert chart_source["repoURL"] == REPOSITORY
    assert chart_source["targetRevision"] == "main"
    assert chart_source["path"] == "helm/afterpush"
    assert chart_source["helm"]["valueFiles"] == [
        "$values/gitops/apps/afterpush-api/values-eks.yaml"
    ]

    assert values_source == {
        "repoURL": REPOSITORY,
        "targetRevision": "main",
        "ref": "values",
    }

    assert application["spec"]["destination"] == {
        "server": "https://kubernetes.default.svc",
        "namespace": "afterpush-dev",
    }
