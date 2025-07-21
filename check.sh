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

pip install --quiet \
    black==25.1.0 \
    ruff==0.12.0 \
    mypy==1.10.0 \
    pytest==8.4.1 \
    jsonschema==4.24.0 \
    fastapi==0.116.1 \
    asgiwebdav==1.5.0 \
    uvicorn==0.35.0 \
    aiofiles==23.2.1 \
    httpx==0.28.1

black --check .
ruff check .
mypy --ignore-missing-imports --strict --explicit-package-bases \
  --no-site-packages --exclude '(acceptance_tests|unit_tests)' \
  main.py shared features
pytest -q features/*/unit_tests
