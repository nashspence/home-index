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
  # In the dev container the virtual environment is /workspace/venv
  source "../venv/bin/activate"
fi

black --check .
ruff check .
mypy --ignore-missing-imports --explicit-package-bases --no-site-packages main.py shared tests || true
mypy --ignore-missing-imports --strict --explicit-package-bases --no-site-packages --exclude '(acceptance_tests|unit_tests)' features/F1
mypy --ignore-missing-imports --strict --explicit-package-bases --no-site-packages --exclude '(acceptance_tests|unit_tests)' features/F2
mypy --ignore-missing-imports --strict --explicit-package-bases --no-site-packages --exclude '(acceptance_tests|unit_tests)' features/F3
mypy --ignore-missing-imports --strict --explicit-package-bases --no-site-packages --exclude '(acceptance_tests|unit_tests)' features/F4
mypy --ignore-missing-imports --strict --explicit-package-bases --no-site-packages --exclude '(acceptance_tests|unit_tests)' features/F5
mypy --ignore-missing-imports --strict --explicit-package-bases --no-site-packages --exclude '(acceptance_tests|unit_tests)' features/F6
pytest -q tests features/*/unit_tests
