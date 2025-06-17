import os
import json
import importlib
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "packages"))


def test_archive_sync_retains_unmounted_docs(tmp_path, monkeypatch):
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

