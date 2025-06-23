"""File hashing helpers for duplicate detection."""

from __future__ import annotations

import math
import os
from pathlib import Path
from typing import Any, Mapping

import xxhash


__all__ = ["truncate_mtime", "compute_hash", "determine_hash"]


def truncate_mtime(mtime: float) -> float:
    """Return ``mtime`` truncated to 4 decimal places for hashing checks."""
    return math.floor(mtime * 10000) / 10000


def compute_hash(path: Path) -> str:
    """Return an xxhash64 digest for ``path``."""
    hasher = xxhash.xxh64()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            hasher.update(chunk)
    return str(hasher.hexdigest())


def determine_hash(
    path: Path,
    index_directory: Path,
    metadata_docs_by_hash: Mapping[str, Any],
    metadata_hashes_by_relpath: Mapping[str, str],
) -> tuple[Path, str, os.stat_result]:
    """Return ``(path, hash, stat)`` using cached hashes when ``mtime`` matches."""
    relpath = str(path.relative_to(index_directory).as_posix())
    stat = path.stat()
    if relpath in metadata_hashes_by_relpath:
        prev_hash = metadata_hashes_by_relpath[relpath]
        prev_mtime = metadata_docs_by_hash[prev_hash]["paths"][relpath]
        if truncate_mtime(stat.st_mtime) == prev_mtime:
            return path, prev_hash, stat
    return path, compute_hash(path), stat
