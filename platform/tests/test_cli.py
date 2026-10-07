import sys
from pathlib import Path

import yaml

from afterpush_engine.pipeline import build_helm_values



PROJECT_ROOT = Path(__file__).resolve().parents[2]
PLATFORM_ROOT = PROJECT_ROOT / "platform"

if str(PLATFORM_ROOT) not in sys.path:
    sys.path.insert(0, str(PLATFORM_ROOT))

from afterpush_cli.main import (
    create_parser,  # noqa: E402
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

def test_deploy_command_discovers_gitops_root(
    tmp_path: Path,
    monkeypatch,
    capsys,
):
    repository_root = tmp_path / "AfterPush"
    gitops_root = repository_root / "gitops" / "apps"
    working_directory = repository_root / "platform"

    gitops_root.mkdir(parents=True)
    working_directory.mkdir(parents=True)

    monkeypatch.chdir(working_directory)

    exit_code = deploy_command(
        config_path=EXAMPLE_PATH,
        gitops_root=None,
    )

    assert exit_code == 0

    values_path = gitops_root / "afterpush-api" / "values.yaml"

    assert values_path.exists()

    captured = capsys.readouterr()

    assert "GitOps deployment prepared" in captured.out
    assert str(values_path) in captured.out


def test_deploy_command_reports_missing_gitops_root(
    tmp_path: Path,
    monkeypatch,
    capsys,
):
    monkeypatch.chdir(tmp_path)

    exit_code = deploy_command(
        config_path=EXAMPLE_PATH,
        gitops_root=None,
    )

    assert exit_code == 1

    captured = capsys.readouterr()

    assert "Could not find gitops/apps" in captured.err
    assert "None" not in captured.err


def test_deploy_command_updates_existing_deployment(
    tmp_path: Path,
    capsys,
):
    gitops_root = tmp_path / "gitops" / "apps"
    values_path = (
        gitops_root
        / "afterpush-api"
        / "values.yaml"
    )

    values_path.parent.mkdir(parents=True)

    values_path.write_text(
        "old: value\n",
        encoding="utf-8",
    )

    exit_code = deploy_command(
        config_path=EXAMPLE_PATH,
        gitops_root=gitops_root,
        allow_update=True,
    )

    assert exit_code == 0

    values = yaml.safe_load(
        values_path.read_text(encoding="utf-8")
    )

    assert values["application"]["name"] == "afterpush-api"
    assert "old" not in values

    captured = capsys.readouterr()

    assert "GitOps deployment prepared" in captured.out


def test_parser_accepts_deploy_update_flag():
    parser = create_parser()

    args = parser.parse_args(
        [
            "deploy",
            "examples/afterpush.yaml",
            "--update",
        ]
    )

    assert args.command == "deploy"
    assert args.update is True


def test_deploy_command_dry_run_does_not_write_gitops_state(
    tmp_path: Path,
    capsys,
):
    gitops_root = tmp_path / "gitops" / "apps"

    exit_code = deploy_command(
        config_path=EXAMPLE_PATH,
        gitops_root=gitops_root,
        dry_run=True,
    )

    assert exit_code == 0

    values_path = (
        gitops_root
        / "afterpush-api"
        / "values.yaml"
    )

    assert not values_path.exists()

    captured = capsys.readouterr()

    assert "afterpush-api" in captured.out
    assert "repository: afterpush-api" in captured.out


def test_parser_accepts_deploy_dry_run_flag():
    parser = create_parser()

    args = parser.parse_args(
        [
            "deploy",
            "examples/afterpush.yaml",
            "--dry-run",
        ]
    )

    assert args.command == "deploy"
    assert args.dry_run is True


def test_deploy_command_dry_run_shows_diff_for_existing_deployment(
    tmp_path: Path,
    capsys,
):
    gitops_root = tmp_path / "gitops" / "apps"

    values_path = (
        gitops_root
        / "afterpush-api"
        / "values.yaml"
    )

    values_path.parent.mkdir(parents=True)

    values_path.write_text(
        "application:\n"
        "  name: afterpush-api\n"
        "image:\n"
        "  repository: old-api\n",
        encoding="utf-8",
    )

    exit_code = deploy_command(
        config_path=EXAMPLE_PATH,
        gitops_root=gitops_root,
        dry_run=True,
    )

    assert exit_code == 0

    captured = capsys.readouterr()

    assert "--- current" in captured.out
    assert "+++ desired" in captured.out
    assert "-  repository: old-api" in captured.out
    assert "+  repository: afterpush-api" in captured.out

    assert "repository: old-api" in values_path.read_text(
        encoding="utf-8"
    )


def test_deploy_command_dry_run_reports_no_changes(
    tmp_path: Path,
    capsys,
):
    gitops_root = tmp_path / "gitops" / "apps"

    values_path = (
        gitops_root
        / "afterpush-api"
        / "values.yaml"
    )

    values_path.parent.mkdir(parents=True)

    values = build_helm_values(EXAMPLE_PATH)

    values_path.write_text(
        yaml.safe_dump(
            values,
            sort_keys=False,
        ),
        encoding="utf-8",
    )

    exit_code = deploy_command(
        config_path=EXAMPLE_PATH,
        gitops_root=gitops_root,
        dry_run=True,
    )

    assert exit_code == 0

    captured = capsys.readouterr()

    assert "No changes detected." in captured.out
