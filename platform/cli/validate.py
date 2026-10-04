import json
import sys
from pathlib import Path

import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[2]
PLATFORM_ROOT = PROJECT_ROOT / "platform"

if str(PLATFORM_ROOT) not in sys.path:
    sys.path.insert(0, str(PLATFORM_ROOT))

from afterpush_engine.validation import (  # noqa: E402
    load_json,
    load_yaml,
    validate_config,
)


def main():
    config_path = (
        Path(sys.argv[1])
        if len(sys.argv) > 1
        else PROJECT_ROOT / "platform/examples/afterpush.yaml"
    )

    schema_path = (
        PROJECT_ROOT / "platform/schema/afterpush.schema.json"
    )

    try:
        config = load_yaml(config_path)
        schema = load_json(schema_path)
    except FileNotFoundError as error:
        print(f"✗ File not found: {error.filename}")
        sys.exit(1)
    except yaml.YAMLError as error:
        print(f"✗ Invalid YAML: {error}")
        sys.exit(1)
    except json.JSONDecodeError as error:
        print(f"✗ Invalid schema JSON: {error}")
        sys.exit(1)

    errors = validate_config(config, schema)

    if errors:
        print("✗ AfterPush configuration is invalid:\n")

        for error in errors:
            print(f"  - {error}")

        sys.exit(1)

    print("✓ AfterPush configuration is valid.")


if __name__ == "__main__":
    main()