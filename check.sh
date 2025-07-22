#!/bin/bash
set -euo pipefail

run() {
  printf ' '
  printf '---- %s ----' "$*"
  "$@"
}

# Run from the repository root so formatting checks don't scan the whole
# container filesystem.
cd "$(dirname "$0")"

# Activate the development virtual environment if it exists so the
# tools installed by `.devcontainer/postStart.sh` are on PATH.
if [ -f "venv/bin/activate" ]; then
  source "venv/bin/activate"
elif [ -f "../venv/bin/activate" ]; then
  # In the dev container the virtual environment is /workspace/venv
  source "../venv/bin/activate"
fi

# Install formatting, linting and test tools if they are not already
# present. This script is also used by `.devcontainer/postStart.sh` so
# the dependency list is maintained in one place.
if [ "${CI:-}" != "true" ]; then
  run "$(dirname "$0")/.devcontainer/install_dev_tools.sh"
fi

run black --check .
run ruff check .
run mypy --ignore-missing-imports --strict --explicit-package-bases \
  --no-site-packages --exclude 'tests' \
  main.py shared features
run pytest -q features/*/tests/unit

if [ "${CI:-}" = "true" ]; then
  mapfile -t test_files < <(find features -path '*/tests/acceptance/test_*.py' | sort -V)
  printf ' '
  printf '---- pytest -vv -x "${test_files[@]}" ----'
  pytest -vv -x "${test_files[@]}"
fi
