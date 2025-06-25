#!/bin/bash
set -euo pipefail

# Run from the repository root so formatting checks don't scan the whole
# container filesystem.
cd "$(dirname "$0")"

# Activate the development virtual environment if it exists so the
# tools installed by `.devcontainer/postStart.sh` are on PATH.
if [ -f "venv/bin/activate" ]; then
  source "venv/bin/activate"
elif [ -f "../venv/bin/activate" ]; then
  # When running inside the dev container the venv lives one directory up
  source "../venv/bin/activate"
fi

black --check .
ruff check .
mypy --python-version 3.11 --ignore-missing-imports --explicit-package-bases --no-site-packages packages tests || true
mypy --python-version 3.11 --ignore-missing-imports --strict --explicit-package-bases --no-site-packages features/F1
mypy --python-version 3.11 --ignore-missing-imports --strict --explicit-package-bases --no-site-packages features/F2
pytest -q
