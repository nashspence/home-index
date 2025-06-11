import importlib
import asyncio
import os
import sys
import subprocess
import time
import uuid

import json
import pytest
import types
import requests
from xmlrpc.server import SimpleXMLRPCServer
from xmlrpc.client import ServerProxy
import multiprocessing

if "meilisearch_python_sdk" in sys.modules:
    del sys.modules["meilisearch_python_sdk"]


def start_meili(port, data_dir):
    proc = subprocess.Popen([
        "meilisearch",
        "--http-addr",
        f"127.0.0.1:{port}",
        "--no-analytics",
        "--db-path",
        str(data_dir),
    ])
    for _ in range(30):
        try:
            r = requests.get(f"http://127.0.0.1:{port}/health")
            if r.status_code == 200:
                break
        except Exception:
            pass
        time.sleep(0.5)
    return proc


@pytest.fixture(scope="session")
def meili_server(tmp_path_factory):
    port = 7701
    data_dir = tmp_path_factory.mktemp("meili_data")
    proc = start_meili(port, data_dir)
    yield f"http://127.0.0.1:{port}"
    proc.terminate()
    proc.wait()


def run_dummy_module(port, name, suffix):
    server = SimpleXMLRPCServer(("127.0.0.1", port), allow_none=True, logRequests=False)

    def hello():
        return json.dumps({"name": name, "version": 1, "filterable_attributes": [], "sortable_attributes": []})

    def check(docs_json):
        docs = json.loads(docs_json)
        return json.dumps([d["id"] for d in docs])

    def run(document_json):
        doc = json.loads(document_json)
        base = {"paths": doc["paths"], "mtime": doc["mtime"], "type": doc["type"], "next": ""}
        return json.dumps([
            doc,
            {**base, "id": f"{doc['id']}_{suffix}a"},
            {**base, "id": f"{doc['id']}_{suffix}b"},
        ])

    server.register_function(hello, "hello")
    server.register_function(check, "check")
    server.register_function(run, "run")
    server.register_function(lambda: None, "load")
    server.register_function(lambda: None, "unload")
    server.serve_forever()


@pytest.fixture(scope="session")
def rpc_modules():
    ports = [8801, 8802, 8803]
    names = ["mod1", "mod2", "mod3"]
    procs = []
    hosts = []
    for port, name in zip(ports, names):
        p = multiprocessing.Process(target=run_dummy_module, args=(port, name, name))
        p.start()
        procs.append(p)
        hosts.append(f"http://127.0.0.1:{port}")

    for host in hosts:
        proxy = ServerProxy(host)
        for _ in range(30):
            try:
                proxy.hello()
                break
            except Exception:
                time.sleep(0.1)
    yield hosts
    for p in procs:
        p.terminate()
        p.join()


def setup_main(tmp_path, monkeypatch, host, index_name, modules=""):
    monkeypatch.setenv("MODULES", modules)
    if "meilisearch_python_sdk" in sys.modules:
        del sys.modules["meilisearch_python_sdk"]
    monkeypatch.setenv("MEILISEARCH_HOST", host)
    monkeypatch.setenv("MEILISEARCH_INDEX_NAME", index_name)
    monkeypatch.setenv("INDEX_DIRECTORY", str(tmp_path / "index"))
    monkeypatch.setenv("MAX_HASH_WORKERS", "1")
    sys.modules["magic"] = types.SimpleNamespace(Magic=lambda mime=True: types.SimpleNamespace(from_file=lambda path: "text/plain"))
    counter = {"c": 0}
    def new_xxh64():
        class H:
            def update(self, data):
                pass

            def hexdigest(self_inner):
                counter["c"] += 1
                return f"hash{counter['c']}"

        return H()

    sys.modules["xxhash"] = types.SimpleNamespace(xxh64=new_xxh64)
    sys.modules["apscheduler.schedulers.background"] = types.SimpleNamespace(BackgroundScheduler=lambda *a, **k: types.SimpleNamespace(add_job=lambda *a, **k: None, start=lambda *a, **k: None))
    sys.modules["apscheduler.triggers.cron"] = types.SimpleNamespace(CronTrigger=lambda **k: None)
    sys.modules["apscheduler.triggers.interval"] = types.SimpleNamespace(IntervalTrigger=lambda **k: None)
    monkeypatch.setenv("METADATA_DIRECTORY", str(tmp_path / "metadata"))
    monkeypatch.setenv("BY_ID_DIRECTORY", str(tmp_path / "metadata" / "by-id"))
    monkeypatch.setenv("BY_PATH_DIRECTORY", str(tmp_path / "metadata" / "by-path"))
    monkeypatch.setenv("ARCHIVE_DIRECTORY", str(tmp_path / "archive"))
    monkeypatch.setenv("LOGGING_DIRECTORY", str(tmp_path / "logs"))
    (tmp_path / "logs").mkdir(parents=True, exist_ok=True)

    from pathlib import Path
    monkeypatch.setattr(Path, "walk", lambda self: ((Path(r), d, f) for r, d, f in os.walk(self)), raising=False)

    from pathlib import Path
    repo_packages = Path(__file__).resolve().parents[1] / "packages"
    sys.path.insert(0, str(repo_packages))
    from home_index import main as hm
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


def test_filter_by_doc_type(tmp_path, monkeypatch, meili_server):
    import json

    index_name = f"test_{uuid.uuid4().hex}"
    hm = setup_main(tmp_path, monkeypatch, meili_server, index_name)

    async def run():
        await hm.init_meili()
        file_doc = {
            "id": "f1",
            "paths": {"a.txt": 0},
            "mtime": 0,
            "size": 1,
            "type": "text/plain",
            "next": "",
            "doc_type": "file",
        }
        content_doc = {
            "id": "c1",
            "paths": {"a.txt": 0},
            "mtime": 0,
            "size": 1,
            "type": "text/plain",
            "next": "",
            "doc_type": "content",
        }
        await hm.add_or_update_document(file_doc)
        await hm.add_or_update_document(content_doc)
        await hm.wait_for_meili_idle()
        files = await hm.index.get_documents(filter="doc_type = file")
        assert [d["id"] for d in files.results] == ["f1"]
        contents = await hm.index.get_documents(filter="doc_type = content")
        assert [d["id"] for d in contents.results] == ["c1"]

    asyncio.run(run())


def test_run_module_multiple_docs(tmp_path, monkeypatch, meili_server):
    import json

    index_name = f"test_{uuid.uuid4().hex}"
    hm = setup_main(tmp_path, monkeypatch, meili_server, index_name)

    async def run():
        await hm.init_meili()
        file_doc = {
            "id": "f1",
            "paths": {"a.txt": 0},
            "mtime": 0,
            "size": 1,
            "type": "text/plain",
            "next": "test",
            "doc_type": "file",
        }
        await hm.add_or_update_document(file_doc)
        await hm.wait_for_meili_idle()

        proxy = DummyProxy([
            {
                "id": "c1",
                "paths": {"a.txt": 0},
                "mtime": 1,
                "type": "text/plain",
                "next": "",
            },
            {
                "id": "c2",
                "paths": {"a.txt": 0},
                "mtime": 1,
                "type": "text/plain",
                "next": "",
            },
        ])

        async def pending(name):
            return [file_doc]

        monkeypatch.setattr(hm, "get_all_pending_jobs", pending)

        await hm.run_module("test", proxy)
        await hm.wait_for_meili_idle()

        docs = await hm.index.get_documents(limit=10)
        ids = {d["id"] for d in docs.results}
        assert {"f1", "c1", "c2"} <= ids
        assert proxy.loaded and proxy.unloaded

    asyncio.run(run())


def test_three_rpc_modules(tmp_path, monkeypatch, meili_server, rpc_modules):
    index_name = f"test_{uuid.uuid4().hex}"
    hm = setup_main(tmp_path, monkeypatch, meili_server, index_name, modules=",".join(rpc_modules))

    async def run():
        for i in range(5):
            path = hm.INDEX_DIRECTORY / f"file{i}.txt"
            path.write_text(str(i))

        await hm.init_meili()
        await hm.sync_documents()

        for module in hm.module_values:
            await hm.run_module(module["name"], module["proxy"])

        await hm.wait_for_meili_idle()
        files = await hm.index.get_documents(filter="doc_type = file", limit=20)
        contents = await hm.index.get_documents(filter="doc_type = content", limit=100)
        assert len(files.results) == 5
        assert len(contents.results) == 30

    asyncio.run(run())
