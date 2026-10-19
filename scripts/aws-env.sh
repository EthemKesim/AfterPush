#!/usr/bin/env bash

# Small, stable entry point for the cost-safe AWS operator workflow.  Keeping
# the policy in Python makes it practical to exercise with local test doubles.
set -euo pipefail

script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
exec python3 "$script_dir/aws_env.py" "$@"
