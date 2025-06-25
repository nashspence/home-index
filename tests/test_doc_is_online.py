import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from features.F3 import archive
import importlib


def test_doc_is_online_returns_false_if_all_paths_missing(tmp_path, monkeypatch):
    index_dir = tmp_path / "index"
    archive_dir = index_dir / "archive"
    index_dir.mkdir(parents=True)
    archive_dir.mkdir()
    monkeypatch.setenv("INDEX_DIRECTORY", str(index_dir))
    monkeypatch.setenv("ARCHIVE_DIRECTORY", str(archive_dir))
    importlib.reload(archive)
    doc = {"paths": {"archive/foo.txt": 1.0}}
    assert not archive.doc_is_online(doc)


def test_doc_is_online_handles_existing_paths(tmp_path, monkeypatch):
    index_dir = tmp_path / "index"
    archive_dir = index_dir / "archive"
    path = archive_dir / "foo.txt"
    path.parent.mkdir(parents=True)
    path.write_text("hi")
    monkeypatch.setenv("INDEX_DIRECTORY", str(index_dir))
    monkeypatch.setenv("ARCHIVE_DIRECTORY", str(archive_dir))
    importlib.reload(archive)
    doc = {"paths": {"archive/foo.txt": 1.0}}
    assert archive.doc_is_online(doc)


def test_doc_is_online_true_for_non_archive_paths(tmp_path, monkeypatch):
    index_dir = tmp_path / "index"
    archive_dir = index_dir / "archive"
    other_path = index_dir / "foo.txt"
    index_dir.mkdir()
    other_path.write_text("hi")
    monkeypatch.setenv("INDEX_DIRECTORY", str(index_dir))
    monkeypatch.setenv("ARCHIVE_DIRECTORY", str(archive_dir))
    importlib.reload(archive)
    doc = {"paths": {"foo.txt": 1.0}}
    assert archive.doc_is_online(doc)
