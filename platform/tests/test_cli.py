import sys
from pathlib import Path

import yaml


PROJECT_ROOT = Path(__file__).resolve().parents[2]
PLATFORM_ROOT = PROJECT_ROOT / "platform"

if str(PLATFORM_ROOT) not in sys.path:
    sys.path.insert(0, str(PLATFORM_ROOT))

from afterpush_cli.main import (  # noqa: E402
    render_command,
    validate_command,
)


EXAMPLE_PATH = PLATFORM_ROOT / "examples/afterpush.yaml"


def create_invalid_config(tmp_path: Path) -> Path:
    config = {
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
            "port": -3000,
            "health": {
                "path": "/health",
            },
        },
    }

    config_path = tmp_path / "invalid-afterpush.yaml"

    config_path.write_text(
        yaml.safe_dump(config, sort_keys=False),
        encoding="utf-8",
    )

    return config_path


def test_validate_command_accepts_valid_config(capsys):
    exit_code = validate_command(EXAMPLE_PATH)

    captured = capsys.readouterr()

    assert exit_code == 0
    assert "AfterPush configuration is valid" in captured.out


def test_validate_command_rejects_invalid_config(tmp_path, capsys):
    config_path = create_invalid_config(tmp_path)

    exit_code = validate_command(config_path)

    captured = capsys.readouterr()

    assert exit_code == 1
    assert "AfterPush configuration is invalid" in captured.err
    assert "spec.port" in captured.err


def test_render_command_generates_values_for_valid_config(capsys):
    exit_code = render_command(EXAMPLE_PATH)

    captured = capsys.readouterr()

    assert exit_code == 0
    assert "application:" in captured.out
    assert "name: demo-api" in captured.out
    assert "targetPort: 3000" in captured.out


def test_render_command_rejects_invalid_config(tmp_path, capsys):
    config_path = create_invalid_config(tmp_path)

    exit_code = render_command(config_path)

    captured = capsys.readouterr()

    assert exit_code == 1
    assert "AfterPush configuration is invalid" in captured.err
    assert "spec.port" in captured.err