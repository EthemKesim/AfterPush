import sys
from pathlib import Path

import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[2]
PLATFORM_ROOT = PROJECT_ROOT / "platform"

if str(PLATFORM_ROOT) not in sys.path:
    sys.path.insert(0, str(PLATFORM_ROOT))

from afterpush_engine.pipeline import (  # noqa: E402
    ConfigurationValidationError,
    build_helm_values,
)


EXAMPLE_PATH = PLATFORM_ROOT / "examples/afterpush.yaml"


def test_pipeline_generates_values_for_valid_config():
    values = build_helm_values(
        config_path=EXAMPLE_PATH,
)

    assert values["application"]["name"] == "afterpush-api"
    assert values["service"]["targetPort"] == 3000
    assert values["probes"]["readiness"]["path"] == "/health"


def test_pipeline_rejects_invalid_config(tmp_path):
    invalid_config = tmp_path / "afterpush-invalid.yaml"

    invalid_config.write_text(
        """
apiVersion: afterpush.dev/v1
kind: Application

metadata:
  name: demo-api

spec:
  image:
    repository: afterpush-api
    tag: metrics

  port: -3000

  health:
    path: /health
""".strip(),
        encoding="utf-8",
    )

    with pytest.raises(ConfigurationValidationError) as error:
        build_helm_values(
            config_path=invalid_config,
        )

    assert any(
        "spec.port" in validation_error
        for validation_error in error.value.errors
    )