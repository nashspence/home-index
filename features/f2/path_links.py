"""Utilities for linking file paths to metadata."""

from __future__ import annotations

import os
from pathlib import Path

from features.f2 import metadata_store


def by_path_directory() -> Path:
    """Return the directory where path links are stored."""
    return Path(
        os.environ.get(
            "BY_PATH_DIRECTORY",
            str(metadata_store.metadata_directory() / "by-path"),
        )
    )


def ensure_directories() -> None:
    """Create required directories if they do not exist."""
    by_path_directory().mkdir(parents=True, exist_ok=True)


def link_path(relpath: str, file_id: str) -> None:
    """Create or update the symlink for ``relpath``."""
    ensure_directories()
    target = metadata_store.by_id_directory() / file_id
    link = by_path_directory() / relpath
    link.parent.mkdir(parents=True, exist_ok=True)
    if link.is_symlink():
        link.unlink()
    relative_target = os.path.relpath(target, link.parent)
    link.symlink_to(relative_target, target_is_directory=True)


def unlink_path(relpath: str) -> None:
    """Remove the symlink for ``relpath`` and clean up empty directories."""
    link = by_path_directory() / relpath
    if link.is_symlink():
        link.unlink()
    parent = link.parent
    if parent != by_path_directory() and parent.exists():
        if not any(parent.iterdir()):
            parent.rmdir()
