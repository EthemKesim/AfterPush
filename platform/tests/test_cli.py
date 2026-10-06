import sys
from pathlib import Path

import yaml


PROJECT_ROOT = Path(__file__).resolve().parents[2]
PLATFORM_ROOT = PROJECT_ROOT / "platform"

if str(PLATFORM_ROOT) not in sys.path:
    sys.path.insert(0, str(PLATFORM_ROOT))

from afterpush_cli.main import (  # noqa: E402
    deploy_command,
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
    assert "name: afterpush-api" in captured.out
    assert "targetPort: 3000" in captured.out


def test_render_command_rejects_invalid_config(tmp_path, capsys):
    config_path = create_invalid_config(tmp_path)

    exit_code = render_command(config_path)

    captured = capsys.readouterr()

    assert exit_code == 1
    assert "AfterPush configuration is invalid" in captured.err
    assert "spec.port" in captured.err


def test_deploy_command_prepares_gitops_values(
    tmp_path: Path,
    capsys,
):
    config_path = (
        Path(__file__).resolve().parents[1]
        / "examples"
        / "afterpush.yaml"
    )

    exit_code = deploy_command(
        config_path=config_path,
        gitops_root=tmp_path,
    )

    assert exit_code == 0

    values_path = tmp_path / "afterpush-api" / "values.yaml"

    assert values_path.exists()

    output = capsys.readouterr()

    assert "GitOps deployment prepared" in output.out
    assert str(values_path) in output.out

def test_deploy_command_refuses_existing_deployment(
    tmp_path: Path,
    capsys,
):
    application_directory = tmp_path / "afterpush-api"
    application_directory.mkdir()

    values_path = application_directory / "values.yaml"
    values_path.write_text(
        "existing: true\n",
        encoding="utf-8",
    )

    exit_code = deploy_command(
        config_path=EXAMPLE_PATH,
        gitops_root=tmp_path,
    )

    captured = capsys.readouterr()

    assert exit_code == 1
    assert "GitOps deployment already exists" in captured.err
    assert values_path.read_text(encoding="utf-8") == "existing: true\n"