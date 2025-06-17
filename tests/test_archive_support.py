import os
import json
import importlib
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "packages"))


def test_metadata_persists_if_the_archive_directory_is_temporarily_missing(tmp_path, monkeypatch):
    log_dir = tmp_path / "logs"
    log_dir.mkdir()
    monkeypatch.setenv("LOGGING_DIRECTORY", str(log_dir))
    index_dir = tmp_path / "index"
    archive_dir = index_dir / "archive"
    meta_dir = tmp_path / "metadata"
    by_id = meta_dir / "by-id"
    by_path = meta_dir / "by-path"

    for d in [index_dir, archive_dir, meta_dir, by_id, by_path]:
        d.mkdir(parents=True, exist_ok=True)

    doc = {
        "id": "hash1",
        "paths": {"archive/foo.txt": 1.0},
        "mtime": 1.0,
        "size": 1,
        "type": "text/plain",
        "next": "",
    }
    doc_dir = by_id / doc["id"]
    doc_dir.mkdir()
    (doc_dir / "document.json").write_text(json.dumps(doc))

    monkeypatch.setenv("INDEX_DIRECTORY", str(index_dir))
    monkeypatch.setenv("METADATA_DIRECTORY", str(meta_dir))
    monkeypatch.setenv("BY_ID_DIRECTORY", str(by_id))
    monkeypatch.setenv("BY_PATH_DIRECTORY", str(by_path))
    monkeypatch.setenv("ARCHIVE_DIRECTORY", str(archive_dir))

    import home_index.main as hi
    importlib.reload(hi)

    md, mhr, ua_docs, ua_hashes = hi.index_metadata()
    assert doc["id"] in ua_docs

    files_docs, hashes = hi.index_files(md, mhr, ua_docs, ua_hashes)
    assert doc["id"] in files_docs


def test_metadata_and_symlinks_are_purged_after_an_archive_file_is_removed(tmp_path, monkeypatch):
    log_dir = tmp_path / "logs2"
    log_dir.mkdir()
    monkeypatch.setenv("LOGGING_DIRECTORY", str(log_dir))
    index_dir = tmp_path / "index"
    archive_dir = index_dir / "archive"
    meta_dir = tmp_path / "metadata"
    by_id = meta_dir / "by-id"
    by_path = meta_dir / "by-path"

    for d in [index_dir, archive_dir, meta_dir, by_id, by_path]:
        d.mkdir(parents=True, exist_ok=True)

    monkeypatch.setenv("INDEX_DIRECTORY", str(index_dir))
    monkeypatch.setenv("METADATA_DIRECTORY", str(meta_dir))
    monkeypatch.setenv("BY_ID_DIRECTORY", str(by_id))
    monkeypatch.setenv("BY_PATH_DIRECTORY", str(by_path))
    monkeypatch.setenv("ARCHIVE_DIRECTORY", str(archive_dir))


    import home_index.main as hi
    import importlib
    importlib.reload(hi)

    doc = {
        "id": "hash1",
        "paths": {"archive/foo.txt": 1.0},
        "mtime": 1.0,
        "size": 1,
        "type": "text/plain",
        "next": "",
    }

    hi.update_metadata({}, {}, {doc["id"]: doc}, {"archive/foo.txt": doc["id"]})
    assert (by_id / doc["id"]).exists()
    assert (by_path / "archive" / "foo.txt").is_symlink()

    hi.update_metadata({doc["id"]: doc}, {"archive/foo.txt": doc["id"]}, {}, {})

    assert not (by_id / doc["id"]).exists()
    assert not (by_path / "archive" / "foo.txt").exists()

