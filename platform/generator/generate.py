import json
import sys
from pathlib import Path

import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[2]
PLATFORM_ROOT = PROJECT_ROOT / "platform"

if str(PLATFORM_ROOT) not in sys.path:
    sys.path.insert(0, str(PLATFORM_ROOT))

from afterpush_engine.pipeline import (  # noqa: E402
    ConfigurationValidationError,
    build_helm_values,
)


def main():
    config_path = (
        Path(sys.argv[1])
        if len(sys.argv) > 1
        else PROJECT_ROOT / "platform/examples/afterpush.yaml"
    )

    try:
        values = build_helm_values(
            config_path=config_path,
        )
    except FileNotFoundError as error:
        print(f"✗ File not found: {error.filename}", file=sys.stderr)
        sys.exit(1)
    except yaml.YAMLError as error:
        print(f"✗ Invalid YAML: {error}", file=sys.stderr)
        sys.exit(1)
    except json.JSONDecodeError as error:
        print(f"✗ Invalid schema JSON: {error}", file=sys.stderr)
        sys.exit(1)
    except ConfigurationValidationError as error:
        print(
            "✗ AfterPush configuration is invalid:\n",
            file=sys.stderr,
        )

        for validation_error in error.errors:
            print(
                f"  - {validation_error}",
                file=sys.stderr,
            )

        sys.exit(1)

    print(
        yaml.safe_dump(
            values,
            sort_keys=False,
        )
    )


if __name__ == "__main__":
    main()