
from pathlib import Path

import yaml


PROJECT_ROOT = Path(__file__).resolve().parents[3]
PLATFORM_ROOT = PROJECT_ROOT / "platform"

MONITORING_VALUES = (
    PLATFORM_ROOT / "addons/monitoring/values.yaml"
)

BLACKBOX_VALUES = (
    PLATFORM_ROOT / "addons/blackbox-exporter/values.yaml"
)

PROBE_TEMPLATE = (
    PROJECT_ROOT / "helm/afterpush/templates/probe.yaml"
)


def load_yaml(path: Path) -> dict:
    with path.open(encoding="utf-8") as file:
        return yaml.safe_load(file)


def test_prometheus_discovers_service_monitors_across_namespaces():
    values = load_yaml(MONITORING_VALUES)
    spec = values["prometheus"]["prometheusSpec"]

    assert spec["serviceMonitorNamespaceSelector"] == {}
    assert spec["serviceMonitorSelector"] == {}
    assert spec["serviceMonitorSelectorNilUsesHelmValues"] is False


def test_prometheus_discovers_probes_across_namespaces():
    values = load_yaml(MONITORING_VALUES)
    spec = values["prometheus"]["prometheusSpec"]

    assert spec["probeNamespaceSelector"] == {}
    assert spec["probeSelector"] == {}
    assert spec["probeSelectorNilUsesHelmValues"] is False


def test_blackbox_exporter_has_afterpush_http_module():
    values = load_yaml(BLACKBOX_VALUES)

    module = values["config"]["modules"]["afterpush_http_2xx"]

    assert module["prober"] == "http"
    assert module["timeout"] == "5s"
    assert module["http"]["follow_redirects"] is True


def test_probe_uses_configured_blackbox_module():
    template = PROBE_TEMPLATE.read_text(encoding="utf-8")

    assert "module: afterpush_http_2xx" in template


def test_probe_uses_expected_blackbox_service():
    template = PROBE_TEMPLATE.read_text(encoding="utf-8")

    assert (
        "blackbox-exporter-prometheus-blackbox-exporter."
        "monitoring.svc.cluster.local:9115"
    ) in template


def test_monitoring_components_are_enabled():
    values = load_yaml(MONITORING_VALUES)

    assert values["prometheus"]["enabled"] is True
    assert values["grafana"]["enabled"] is True
    assert values["alertmanager"]["enabled"] is True

