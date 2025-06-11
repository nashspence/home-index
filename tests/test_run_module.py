import types
import sys
import asyncio
import json
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
    import importlib
    importlib.reload(hm)
    return hm


class DummyProxy:
    def __init__(self, result):
        self._result = result
        self.loaded = False
        self.unloaded = False

    def load(self):
        self.loaded = True

    def run(self, document_json):
        return json.dumps(self._result)

    def unload(self):
        self.unloaded = True

    def check(self, docs):
        return json.dumps([])


def test_run_module_handles_single_document(tmp_path, monkeypatch):
    hm = setup_main(tmp_path, monkeypatch)

    processed = []

    async def update(doc):
        processed.append(doc)

    async def pending(name):
        return [{"id": "1", "paths": {"a.txt": 0}, "mtime": 0, "type": "text/plain", "next": ""}]

    async def wait():
        return None

    monkeypatch.setattr(hm, "get_all_pending_jobs", pending)
    monkeypatch.setattr(hm, "update_doc_from_module", update)
    monkeypatch.setattr(hm, "wait_for_meili_idle", wait)

    proxy = DummyProxy({"id": "1", "paths": {"a.txt": 0}, "mtime": 0, "type": "text/plain", "next": ""})
    asyncio.run(hm.run_module("test", proxy))

    assert proxy.loaded and proxy.unloaded
    assert len(processed) == 1


def test_run_module_handles_multiple_documents(tmp_path, monkeypatch):
    hm = setup_main(tmp_path, monkeypatch)

    processed = []

    async def update(doc):
        processed.append(doc)

    async def pending(name):
        return [{"id": "1", "paths": {"a.txt": 0}, "mtime": 0, "type": "text/plain", "next": ""}]

    async def wait():
        return None

    monkeypatch.setattr(hm, "get_all_pending_jobs", pending)
    monkeypatch.setattr(hm, "update_doc_from_module", update)
    monkeypatch.setattr(hm, "wait_for_meili_idle", wait)

    proxy = DummyProxy([
        {"id": "1a", "paths": {"a.txt": 0}, "mtime": 0, "type": "text/plain", "next": ""},
        {"id": "1b", "paths": {"a.txt": 0}, "mtime": 0, "type": "text/plain", "next": ""},
    ])
    asyncio.run(hm.run_module("test", proxy))

    assert proxy.loaded and proxy.unloaded
    assert len(processed) == 2
