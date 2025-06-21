#!/bin/bash
set -euo pipefail

# Activate the development virtual environment if it exists so the
# tools installed by `.devcontainer/poststart.sh` are on PATH.
if [ -f "/workspace/venv/bin/activate" ]; then
  source /workspace/venv/bin/activate
fi

black --check .
ruff check .
