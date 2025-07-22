#!/bin/bash
set -euo pipefail

DESC="$1"; shift
LOGFILE="$(mktemp)"

# Print start message
echo "$DESC started"

# Run command, capture output
if "$@" >"$LOGFILE" 2>&1; then
    grep -iE '(warning|error)' "$LOGFILE" >&2 || true
    echo "$DESC completed successfully"
else
    echo "$DESC failed" >&2
    cat "$LOGFILE" >&2
    exit 1
fi
