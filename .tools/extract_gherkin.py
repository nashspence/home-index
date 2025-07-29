#!/usr/bin/env python3
from __future__ import annotations
import hashlib
import re
import sys
from pathlib import Path
import textwrap
import shutil

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "features"
OUT = ROOT / ".pytest_cache" / "md_features"

START_FENCE = re.compile(r"^```(?:gherkin|feature)\s*$", re.IGNORECASE)
END_FENCE = re.compile(r"^```\s*$")
FEATURE_HDR = re.compile(r"(?m)^\s*Feature\s*:\s*")


def normalize_newlines(text: str) -> str:
    return text.replace("\r\n", "\n").replace("\r", "\n")


def extract_blocks(md_text: str) -> list[str]:
    lines = normalize_newlines(md_text).splitlines()
    blocks: list[list[str]] = []
    cur: list[str] | None = None
    in_block = False
    for line in lines:
        if not in_block and START_FENCE.match(line):
            in_block = True
            cur = []
            continue
        if in_block and END_FENCE.match(line):
            in_block = False
            blocks.append(cur or [])
            cur = None
            continue
        if in_block and cur is not None:
            cur.append(line)
    cleaned = []
    for b in blocks:
        block = "\n".join(b)
        block = textwrap.dedent(block)
        block = "\n".join(line.lstrip() for line in block.splitlines())
        cleaned.append(block.strip() + "\n")
    return cleaned


def write_feature(feature_dir: Path, prefix: str, idx: int, content: str) -> None:
    count = len(FEATURE_HDR.findall(content))
    if count != 1:
        raise SystemExit(
            f"{feature_dir} block {idx} must contain exactly one 'Feature:' header (found {count})."
        )
    h = hashlib.sha1(content.encode("utf-8")).hexdigest()[:12]
    feature_dir.mkdir(parents=True, exist_ok=True)
    (feature_dir / f"{prefix}_{idx:02d}_{h}.feature").write_text(
        content, encoding="utf-8"
    )


def main() -> int:
    if OUT.exists():
        shutil.rmtree(OUT)
    OUT.mkdir(parents=True, exist_ok=True)
    written = 0
    for spec in SRC.rglob("SPEC.md"):
        feature_name = spec.parent.name
        blocks = extract_blocks(spec.read_text(encoding="utf-8"))
        for i, block in enumerate(blocks, 1):
            dest = OUT / feature_name
            write_feature(dest, feature_name, i, block)
            written += 1
    print(f"Wrote {written} .feature files under {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
