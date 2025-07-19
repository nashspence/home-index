import importlib
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import pytest

from features.F3 import archive


def _reload(monkeypatch: "pytest.MonkeyPatch", index_dir: Path) -> None:
    monkeypatch.setenv("INDEX_DIRECTORY", str(index_dir))
    monkeypatch.setenv("ARCHIVE_DIRECTORY", str(index_dir / "archive"))
    importlib.reload(archive)


def test_path_from_relpath_and_is_in_archive_dir(tmp_path, monkeypatch):
    index_dir = tmp_path / "index"
    archive_dir = index_dir / "archive"
    archive_dir.mkdir(parents=True)
    _reload(monkeypatch, index_dir)
    rel = "archive/drive/foo.txt"
    path = archive.path_from_relpath(rel)
    assert path == index_dir / rel
    assert archive.is_in_archive_dir(path)
    assert not archive.is_in_archive_dir(index_dir / "other.txt")


def test_drive_name_from_path(tmp_path, monkeypatch):
    index_dir = tmp_path / "index"
    archive_dir = index_dir / "archive"
    drive_dir = archive_dir / "drive1"
    drive_dir.mkdir(parents=True)
    _reload(monkeypatch, index_dir)
    assert archive.drive_name_from_path(drive_dir / "foo.txt") == "drive1"
    assert archive.drive_name_from_path(archive_dir) is None
    assert archive.drive_name_from_path(index_dir / "foo.txt") is None


def test_update_archive_flags(tmp_path, monkeypatch):
    index_dir = tmp_path / "index"
    archive_dir = index_dir / "archive"
    drive_dir = archive_dir / "drive1"
    drive_dir.mkdir(parents=True)
    (index_dir / "foo.txt").write_text("hi")
    _reload(monkeypatch, index_dir)
    doc = {"paths": {"foo.txt": 1.0}}
    archive.update_archive_flags(doc)
    assert doc["has_archive_paths"] is False
    assert doc["offline"] is False
    doc2 = {"paths": {"archive/drive1/bar.txt": 1.0}}
    archive.update_archive_flags(doc2)
    assert doc2["has_archive_paths"] is True
    assert doc2["offline"] is True
    (drive_dir / "bar.txt").write_text("hi")
    archive.update_archive_flags(doc2)
    assert doc2["offline"] is False


def test_is_status_marker_and_pending_branch(tmp_path, monkeypatch):
    index_dir = tmp_path / "index"
    archive_dir = index_dir / "archive"
    drive_dir = archive_dir / "drive1"
    drive_dir.mkdir(parents=True)
    pending = archive_dir / "drive1-status-pending"
    pending.write_text("ts")
    _reload(monkeypatch, index_dir)
    assert archive.is_status_marker(pending)
    doc = {"id": "1", "paths": {"archive/drive1/foo.txt": 1.0}, "next": ""}
    archive.update_drive_markers({"1": doc})
    ready = archive_dir / "drive1-status-ready"
    assert ready.exists()
    assert not pending.exists()


def test_update_drive_markers_skips_unreferenced(tmp_path, monkeypatch):
    index_dir = tmp_path / "index"
    archive_dir = index_dir / "archive"
    archive_dir.mkdir(parents=True)
    (archive_dir / "drive1-status-ready").write_text("ts")
    _reload(monkeypatch, index_dir)
    doc = {"id": "1", "paths": {"foo.txt": 1.0}}
    archive.update_drive_markers({"1": doc})
    assert not (archive_dir / "drive1-status-ready").exists()
