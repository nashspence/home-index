import importlib
from pathlib import Path
from types import SimpleNamespace

import pytest


def _reload_hi(
    monkeypatch: "pytest.MonkeyPatch", index_dir: Path, meta_dir: Path
) -> SimpleNamespace:
    monkeypatch.setenv("INDEX_DIRECTORY", str(index_dir))
    monkeypatch.setenv("ARCHIVE_DIRECTORY", str(index_dir / "archive"))
    monkeypatch.setenv("METADATA_DIRECTORY", str(meta_dir))
    monkeypatch.setenv("BY_ID_DIRECTORY", str(meta_dir / "by-id"))
    monkeypatch.setenv("BY_PATH_DIRECTORY", str(meta_dir / "by-path"))
    from features.F1 import sync
    from features.F3 import archive
    from features.F2 import duplicate_finder
    from features.F4 import modules as modules_f4

    importlib.reload(sync)
    importlib.reload(archive)
    return SimpleNamespace(
        archive=archive,
        index_metadata=sync.index_metadata,
        index_files=sync.index_files,
        update_metadata=sync.update_metadata,
        duplicate_finder=duplicate_finder,
        modules_f4=modules_f4,
    )


def test_update_drive_markers_creates_ready(tmp_path, monkeypatch):
    index_dir = tmp_path / "index"
    drive = index_dir / "archive" / "drive1"
    drive.mkdir(parents=True)
    meta_dir = tmp_path / "meta"
    (meta_dir / "by-id").mkdir(parents=True)
    (meta_dir / "by-path").mkdir()
    hi = _reload_hi(monkeypatch, index_dir, meta_dir)

    doc = {
        "id": "1",
        "paths": {"archive/drive1/foo.txt": 1.0},
        "mtime": 1.0,
        "size": 1,
        "type": "text/plain",
        "next": "",
    }
    hi.archive.update_drive_markers({"1": doc})
    ready = index_dir / "archive" / "drive1-status-ready"
    pending = index_dir / "archive" / "drive1-status-pending"
    assert ready.exists()
    assert not pending.exists()


def test_update_drive_markers_pending(tmp_path, monkeypatch):
    index_dir = tmp_path / "index"
    drive = index_dir / "archive" / "drive1"
    drive.mkdir(parents=True)
    meta_dir = tmp_path / "meta"
    (meta_dir / "by-id").mkdir(parents=True)
    (meta_dir / "by-path").mkdir()
    hi = _reload_hi(monkeypatch, index_dir, meta_dir)

    doc = {
        "id": "1",
        "paths": {"archive/drive1/foo.txt": 1.0},
        "mtime": 1.0,
        "size": 1,
        "type": "text/plain",
        "next": "mod",
    }
    hi.archive.update_drive_markers({"1": doc})
    ready = index_dir / "archive" / "drive1-status-ready"
    pending = index_dir / "archive" / "drive1-status-pending"
    assert pending.exists()
    assert not ready.exists()


def test_update_drive_markers_no_drive(tmp_path, monkeypatch):
    index_dir = tmp_path / "index"
    (index_dir / "archive").mkdir(parents=True)
    meta_dir = tmp_path / "meta"
    (meta_dir / "by-id").mkdir(parents=True)
    (meta_dir / "by-path").mkdir()
    hi = _reload_hi(monkeypatch, index_dir, meta_dir)

    doc = {
        "id": "1",
        "paths": {"archive/drive1/foo.txt": 1.0},
        "mtime": 1.0,
        "size": 1,
        "type": "text/plain",
        "next": "",
    }
    hi.archive.update_drive_markers({"1": doc})
    ready = index_dir / "archive" / "drive1-status-ready"
    pending = index_dir / "archive" / "drive1-status-pending"
    assert not ready.exists()
    assert not pending.exists()


def test_index_files_skips_status_files(tmp_path, monkeypatch):
    index_dir = tmp_path / "index"
    archive_dir = index_dir / "archive"
    drive = archive_dir / "drive1"
    drive.mkdir(parents=True)
    (archive_dir / "drive1-status-ready").write_text("t")
    file_path = drive / "foo.txt"
    file_path.write_text("hi")

    meta_dir = tmp_path / "meta"
    by_id = meta_dir / "by-id"
    by_path = meta_dir / "by-path"
    by_id.mkdir(parents=True)
    by_path.mkdir()

    hi = _reload_hi(monkeypatch, index_dir, meta_dir)

    md, mhr, ua_docs, ua_hashes, _ = hi.index_metadata()
    files_docs, hashes = hi.index_files(md, mhr, ua_docs, ua_hashes)
    assert len(files_docs) == 1
    assert next(iter(files_docs.values()))["id"] == hi.duplicate_finder.compute_hash(
        file_path
    )
    assert all(
        "status-ready" not in p for p in next(iter(files_docs.values()))["paths"]
    )


def test_update_drive_markers_preserves_offline_marker(tmp_path, monkeypatch):
    index_dir = tmp_path / "index"
    archive_dir = index_dir / "archive"
    archive_dir.mkdir(parents=True)
    marker = archive_dir / "drive1-status-ready"
    marker.write_text("ts")

    meta_dir = tmp_path / "meta"
    (meta_dir / "by-id").mkdir(parents=True)
    (meta_dir / "by-path").mkdir()

    hi = _reload_hi(monkeypatch, index_dir, meta_dir)

    doc = {
        "id": "1",
        "paths": {"archive/drive1/foo.txt": 1.0},
        "mtime": 1.0,
        "size": 1,
        "type": "text/plain",
        "next": "",
    }
    hi.archive.update_drive_markers({"1": doc})

    assert marker.exists()


def test_update_drive_markers_offline_pending_on_modules_change(
    tmp_path, monkeypatch
) -> None:
    index_dir = tmp_path / "index"
    archive_dir = index_dir / "archive"
    archive_dir.mkdir(parents=True)
    ready = archive_dir / "drive1-status-ready"
    ready.write_text("ts")

    meta_dir = tmp_path / "meta"
    (meta_dir / "by-id").mkdir(parents=True)
    (meta_dir / "by-path").mkdir()

    hi = _reload_hi(monkeypatch, index_dir, meta_dir)
    monkeypatch.setattr(hi.modules_f4, "is_modules_changed", True)

    doc = {
        "id": "1",
        "paths": {"archive/drive1/foo.txt": 1.0},
        "mtime": 1.0,
        "size": 1,
        "type": "text/plain",
        "next": "mod",
    }
    hi.archive.update_drive_markers({"1": doc})

    pending = archive_dir / "drive1-status-pending"
    assert pending.exists()
    assert not ready.exists()


def test_update_drive_markers_removes_orphan_marker(tmp_path, monkeypatch):
    index_dir = tmp_path / "index"
    archive_dir = index_dir / "archive"
    archive_dir.mkdir(parents=True)
    marker = archive_dir / "drive1-status-ready"
    marker.write_text("ts")

    meta_dir = tmp_path / "meta"
    (meta_dir / "by-id").mkdir(parents=True)
    (meta_dir / "by-path").mkdir()

    hi = _reload_hi(monkeypatch, index_dir, meta_dir)

    hi.archive.update_drive_markers({})

    assert not marker.exists()
