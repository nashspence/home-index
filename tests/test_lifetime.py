import importlib
import sys
import types
import os
from collections import defaultdict
import asyncio


def setup_main(tmp_path, monkeypatch):
    sys.modules['magic'] = types.SimpleNamespace(Magic=lambda mime=True: types.SimpleNamespace(from_file=lambda path: 'text/plain'))
    sys.modules['xxhash'] = types.SimpleNamespace(xxh64=lambda: types.SimpleNamespace(update=lambda x: None, hexdigest=lambda: 'hash'))
    sys.modules['apscheduler.schedulers.background'] = types.SimpleNamespace(BackgroundScheduler=lambda *a, **k: types.SimpleNamespace(add_job=lambda *a, **k: None, start=lambda *a, **k: None))
    sys.modules['apscheduler.triggers.cron'] = types.SimpleNamespace(CronTrigger=lambda **k: None)
    sys.modules['apscheduler.triggers.interval'] = types.SimpleNamespace(IntervalTrigger=lambda **k: None)
    sys.modules['meilisearch_python_sdk'] = types.SimpleNamespace(AsyncClient=lambda *a, **k: None)
    monkeypatch.setenv("MODULES", "")
    monkeypatch.setenv("INDEX_DIRECTORY", str(tmp_path / "index"))
    monkeypatch.setenv("METADATA_DIRECTORY", str(tmp_path / "metadata"))
    monkeypatch.setenv("BY_ID_DIRECTORY", str(tmp_path / "metadata" / "by-id"))
    monkeypatch.setenv("BY_PATH_DIRECTORY", str(tmp_path / "metadata" / "by-path"))
    monkeypatch.setenv("ARCHIVE_DIRECTORY", str(tmp_path / "archive"))
    monkeypatch.setenv("LOGGING_DIRECTORY", str(tmp_path / "logs"))
    (tmp_path / "logs").mkdir(parents=True, exist_ok=True)

    from pathlib import Path
    repo_packages = Path(__file__).resolve().parents[1] / "packages"
    sys.path.insert(0, str(repo_packages))
    from home_index import main as hm
    importlib.reload(hm)
    return hm


def test_deleted_file_removes_content_docs(tmp_path, monkeypatch):
    hm = setup_main(tmp_path, monkeypatch)
    from pathlib import Path
    monkeypatch.setattr(Path, "walk", lambda self: ((Path(r), d, f) for r, d, f in os.walk(self)), raising=False)

    file_doc = {"id": "f1", "paths": {"a.txt": 0}, "mtime": 0, "size": 1, "type": "text/plain", "next": "", "doc_type": "file"}
    content_doc = {"id": "c1", "paths": {"a.txt": 0}, "mtime": 0, "size": 1, "type": "text/plain", "next": "", "doc_type": "content"}
    hm.write_doc_json(file_doc)
    hm.write_doc_json(content_doc)
    by_path = hm.BY_PATH_DIRECTORY / "a.txt"
    by_path.mkdir(parents=True, exist_ok=True)
    for doc in (file_doc, content_doc):
        link = by_path / doc["id"]
        target = os.path.relpath(hm.BY_ID_DIRECTORY / doc["id"], link.parent)
        link.symlink_to(target, target_is_directory=True)

    (hm.INDEX_DIRECTORY).mkdir(parents=True, exist_ok=True)
    md_docs, md_relpaths, ua_docs, ua_relpaths = hm.index_metadata()
    files_docs, files_relpaths = hm.index_files(md_docs, md_relpaths, ua_docs, ua_relpaths)
    hm.update_metadata(md_docs, md_relpaths, files_docs, files_relpaths)

    assert not (hm.BY_ID_DIRECTORY / "f1").exists()
    assert not (hm.BY_ID_DIRECTORY / "c1").exists()
    assert not (hm.BY_PATH_DIRECTORY / "a.txt").exists()
