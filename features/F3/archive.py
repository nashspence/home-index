from __future__ import annotations

import os
from pathlib import Path

__all__ = [
    "archive_directory",
    "path_from_relpath",
    "is_in_archive_dir",
    "doc_is_online",
]


def index_directory() -> Path:
    return Path(os.environ.get("INDEX_DIRECTORY", "/files"))


def archive_directory() -> Path:
    return Path(os.environ.get("ARCHIVE_DIRECTORY", str(index_directory() / "archive")))


def path_from_relpath(relpath: str) -> Path:
    return index_directory() / relpath


def is_in_archive_dir(path: Path) -> bool:
    return archive_directory() in path.parents


def doc_is_online(doc: dict) -> bool:
    """Return True if ``doc`` has at least one path accessible on disk."""
    for relpath in doc.get("paths", {}).keys():
        path = path_from_relpath(relpath)
        if not is_in_archive_dir(path) or path.exists():
            return True
    return False
