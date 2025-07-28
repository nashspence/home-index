#!/usr/bin/env bash
set -euo pipefail

# Extract gherkin snippets from tracked Markdown files and lint them

tmp="$(mktemp -d)"; trap 'rm -rf "$tmp"' EXIT

git ls-files -z '*.md' | while IFS= read -r -d '' md; do
  awk -v src="$md" -v out="$tmp" '
    BEGIN { inside=0; n=0 }
    /^```[[:space:]]*(gherkin|cucumber|feature)([[:space:]]|$)/ {
      inside=1; n++; fn=sprintf("%s/%s.%03d.feature", out, src, n);
      dir=fn; sub(/[^/]+$/, "", dir); system("mkdir -p \"" dir "\"");
      print "# Source: " src " (block " n ")" > fn; next
    }
    inside && /^```[[:space:]]*$/ { inside=0; close(fn); next }
    inside { print >> fn }
  ' "$md"
done

find "$tmp" -name '*.feature' -print0 | xargs -0 -r npx -y gherkin-lint -c .gherkin-lintrc
