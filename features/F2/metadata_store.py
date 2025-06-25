"""Utilities for storing metadata by file ID."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import MutableMapping, Any


def _add_paths_list(doc: MutableMapping[str, Any]) -> None:
    """Populate ``paths_list`` and update the schema version."""
    doc["paths_list"] = sorted(doc.get("paths", {}).keys())
    doc["version"] = 1


def metadata_directory() -> Path:
    """Return the root metadata directory."""
    return Path(os.environ.get("METADATA_DIRECTORY", "/files/metadata"))


def by_id_directory() -> Path:
    """Return the directory where metadata is stored by file ID."""
    return Path(os.environ.get("BY_ID_DIRECTORY", str(metadata_directory() / "by-id")))


def ensure_directories() -> None:
    """Create required directories if they do not exist."""
    for path in [metadata_directory(), by_id_directory()]:
        path.mkdir(parents=True, exist_ok=True)


def write_doc_json(doc: MutableMapping[str, Any]) -> None:
    """Write ``doc`` as JSON under ``BY_ID_DIRECTORY``."""
    ensure_directories()
    target_dir = by_id_directory() / str(doc["id"])
    target_dir.mkdir(parents=True, exist_ok=True)
    with (target_dir / "document.json").open("w") as f:
        json.dump(doc, f, indent=4, separators=(", ", ": "))
