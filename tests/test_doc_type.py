import importlib
import types
import sys
import asyncio
import os
from collections import defaultdict

import pytest


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


def test_index_files_sets_doc_type(tmp_path, monkeypatch):
    hm = setup_main(tmp_path, monkeypatch)
    from pathlib import Path
    monkeypatch.setattr(Path, "walk", lambda self: ((Path(r), d, f) for r, d, f in os.walk(self)), raising=False)
    hm.INDEX_DIRECTORY.mkdir(parents=True, exist_ok=True)
    file_path = hm.INDEX_DIRECTORY / "test.txt"
    file_path.write_text("hi")

    docs, _ = hm.index_files({}, defaultdict(set), {}, defaultdict(set))
    assert list(docs.values())[0]["doc_type"] == "file"


def test_update_doc_from_module_defaults_content(tmp_path, monkeypatch):
    hm = setup_main(tmp_path, monkeypatch)

    async def noop(*args, **kwargs):
        return None

    monkeypatch.setattr(hm, "write_doc_json", lambda doc: None)
    monkeypatch.setattr(hm, "add_or_update_document", noop)

    doc = {"id": "1", "paths": {"a.txt": 0}, "next": "", "type": "text/plain"}
    asyncio.run(hm.update_doc_from_module(doc))
    assert doc["doc_type"] == "content"
