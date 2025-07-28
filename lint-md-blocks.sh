#!/usr/bin/env bash
set -euo pipefail

# Usage: lint-md-blocks.sh "cmd {}" tag files...
cmd_template=$1
block_tag=$2
shift 2

workdir="$(mktemp -d)"
trap 'rm -rf "$workdir"' EXIT

for md in "$@"; do
  awk -v src="$md" -v out="$workdir" -v tag="$block_tag" '
    BEGIN { inside=0; n=0; pattern="^```[[:space:]]*" tag "([[:space:]]|$)" }
    $0 ~ pattern {
      inside=1; n++; fn=sprintf("%s/%s.%03d.feature", out, src, n);
      dir=fn; sub(/[^/]+$/, "", dir); system("mkdir -p \"" dir "\"");
      print "# Source: " src " (block " n ")" > fn; next
    }
    inside && /^```[[:space:]]*$/ { inside=0; close(fn); next }
    inside { print >> fn }
  ' "$md"
done

find "$workdir" -type f | while IFS= read -r snippet; do
  cmd=${cmd_template//\{\}/"$snippet"}
  bash -c "$cmd"
done
