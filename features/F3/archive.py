from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path
from typing import Any, Mapping, MutableMapping

__all__ = [
    "archive_directory",
    "path_from_relpath",
    "is_in_archive_dir",
    "doc_is_online",
    "update_archive_flags",
    "is_status_marker",
    "drive_name_from_path",
    "update_drive_markers",
]


def index_directory() -> Path:
    return Path(os.environ.get("INDEX_DIRECTORY", "/files"))


def archive_directory() -> Path:
    return Path(os.environ.get("ARCHIVE_DIRECTORY", str(index_directory() / "archive")))


def path_from_relpath(relpath: str) -> Path:
    return index_directory() / relpath


def is_in_archive_dir(path: Path) -> bool:
    return archive_directory() in path.parents


def doc_is_online(doc: Mapping[str, Any]) -> bool:
    """Return True if ``doc`` has at least one path accessible on disk."""
    for relpath in doc.get("paths", {}).keys():
        path = path_from_relpath(relpath)
        if not is_in_archive_dir(path) or path.exists():
            return True
    return False


def update_archive_flags(doc: MutableMapping[str, Any]) -> None:
    """Populate archive-related flags on ``doc`` in place."""
    doc["has_archive_paths"] = any(
        is_in_archive_dir(path_from_relpath(relpath))
        for relpath in doc.get("paths", {}).keys()
    )
    doc["offline"] = not doc_is_online(doc)


STATUS_READY_SUFFIX = "-status-ready"
STATUS_PENDING_SUFFIX = "-status-pending"


def is_status_marker(path: Path) -> bool:
    """Return True if ``path`` is an archive status marker."""
    return path.parent == archive_directory() and (
        path.name.endswith(STATUS_READY_SUFFIX)
        or path.name.endswith(STATUS_PENDING_SUFFIX)
    )


def drive_name_from_path(path: Path) -> str | None:
    """Return the archive drive name for ``path`` or ``None``."""
    try:
        relative = path.relative_to(archive_directory())
    except ValueError:
        return None
    if relative.parts:
        return relative.parts[0]
    return None


def _marker_path(drive: str, pending: bool) -> Path:
    suffix = STATUS_PENDING_SUFFIX if pending else STATUS_READY_SUFFIX
    return archive_directory() / f"{drive}{suffix}"


def update_drive_markers(docs: Mapping[str, Mapping[str, Any]]) -> None:
    """Update drive status marker files based on ``docs``.

    Markers are updated for all referenced drives. Offline drives retain their
    timestamp unless work is queued for them (e.g. after a module update).
    """
    drives_present = {d.name for d in archive_directory().iterdir() if d.is_dir()}
    drives_referenced: set[str] = set()
    pending_map: dict[str, bool] = {}
    for doc in docs.values():
        for relpath in doc.get("paths", {}).keys():
            path = path_from_relpath(relpath)
            drive = drive_name_from_path(path)
            if not drive:
                continue
            drives_referenced.add(drive)
            if doc.get("next"):
                pending_map[drive] = True

    for marker in archive_directory().iterdir():
        if is_status_marker(marker):
            name = marker.name
            if name.endswith(STATUS_READY_SUFFIX):
                drive = name[: -len(STATUS_READY_SUFFIX)]
            elif name.endswith(STATUS_PENDING_SUFFIX):
                drive = name[: -len(STATUS_PENDING_SUFFIX)]
            else:
                continue
            if drive not in drives_referenced:
                marker.unlink()

    timestamp = datetime.utcnow().replace(microsecond=0).isoformat() + "Z"
    for drive in drives_referenced:
        pending = pending_map.get(drive, False)
        if drive in drives_present or pending:
            marker = _marker_path(drive, pending)
            other = _marker_path(drive, not pending)
            marker.write_text(timestamp)
            if other.exists():
                other.unlink()
