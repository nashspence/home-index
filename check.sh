#!/usr/bin/env bash
# ci/check.sh – run formatting, linting, and tests locally or in CI
set -euo pipefail
IFS=$'\n\t'

###############################################################################
# Helpers
###############################################################################
# Standard runner
run() {
  local IFS=' '               # headings use spaces, not newlines
  local heading="$*"

  if [[ ${GITHUB_ACTIONS:-} == "true" ]]; then
    echo "::group::$heading"
  else
    printf '\n\033[1m---- %s ----\033[0m\n' "$heading"
  fi

  "$@"
  local status=$?
  [[ ${GITHUB_ACTIONS:-} == "true" ]] && echo "::endgroup::"
  return "$status"
}

# Named runner: first arg is the label
run_named() {
  local label=$1; shift
  if [[ ${GITHUB_ACTIONS:-} == "true" ]]; then
    echo "::group::$label"
  else
    printf '\n\033[1m---- %s ----\033[0m\n' "$label"
  fi
  "$@"
  local status=$?
  [[ ${GITHUB_ACTIONS:-} == "true" ]] && echo "::endgroup::"
  return "$status"
}

###############################################################################
# Environment setup
###############################################################################
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" &>/dev/null && pwd)"
cd "$SCRIPT_DIR"

for venv in "venv" "../venv"; do
  [[ -f "$venv/bin/activate" ]] && source "$venv/bin/activate" && break
done

if [[ ${GITHUB_ACTIONS:-false} != "true" ]]; then
  run "$SCRIPT_DIR/.devcontainer/install_dev_tools.sh"
fi

###############################################################################
# Fast checks (always)
###############################################################################
run black --check .
run ruff check .
run mypy --ignore-missing-imports --strict --explicit-package-bases \
         --no-site-packages --exclude tests \
         main.py shared features
run mdsf verify --config mdsf.json features/F1/SPEC.md
run "$SCRIPT_DIR/gherkin-lint-md.sh"

# Unit tests – concise header
run_named "pytest unit (-q)" \
          pytest -q features/*/tests/unit

###############################################################################
# Acceptance tests (CI only)
###############################################################################
if [[ ${GITHUB_ACTIONS:-false} == "true" ]]; then
  mapfile -t test_files < <(
    find features -path '*/tests/acceptance/*' -name 'test_*.py' | sort -V
  )
  run_named "pytest acceptance (-vv -x -s)" \
            pytest -vv -x -s "${test_files[@]}"
fi
