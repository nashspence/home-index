import asyncio
import json
from pathlib import Path


def test_service_module_queue_processes_segment_content(monkeypatch):
    import importlib

    from features.F4 import modules as modules_f4
    from features.F2 import search_index
    from features.F5 import chunking

    importlib.reload(modules_f4)
    importlib.reload(search_index)
    importlib.reload(chunking)

    doc = {"id": "file1", "mtime": 1.0, "paths": {"a.txt": 1.0}, "next": ""}

    async def fake_get_jobs(name):
        return [doc]

    recorded = {}

    async def fake_add_chunks(docs):
        recorded["chunks"] = docs

    async def fake_update_doc(d):
        recorded["updated"] = d

    async def fake_delete(fid, mod):
        recorded["deleted"] = (fid, mod)

    async def fake_wait():
        recorded["wait"] = True

    class DummyRedis:
        def __init__(self):
            self.storage = {
                "mod:check": [],
                "mod:run": [],
                "modules:done": [
                    json.dumps(
                        {
                            "module": "mod",
                            "document": doc,
                            "content": [{"text": "hello"}],
                        }
                    )
                ],
                "mod:check:processing": {},
                "mod:run:processing": {},
                "timeouts": {},
            }

        def rpush(self, key, val):
            if key.endswith(":check") or key.endswith(":run"):
                self.storage.setdefault(key, []).append(val)
            else:
                recorded["pushed"] = val

        def lpop(self, key):
            recorded["lpop"] = True
            if self.storage[key]:
                return self.storage[key].pop(0)
            return None

        def zrangebyscore(self, key, _min, _max):
            return []

        def lrange(self, key, _start, _end):
            return list(self.storage.get(key, []))

        def zrange(self, key, _start, _end):
            return list(self.storage.get(key, []))

        def zrem(self, key, member):
            pass

        class Pipeline:
            def __init__(self, client: "DummyRedis") -> None:
                self.client = client

            def zadd(self, *args, **kwargs):
                self.client.zadd(*args, **kwargs)

            def rpush(self, *args, **kwargs):
                self.client.rpush(*args, **kwargs)

            def lrem(self, *args, **kwargs):
                self.client.lrem(*args, **kwargs)

            def zrem(self, *args, **kwargs):
                self.client.zrem(*args, **kwargs)

            def execute(self) -> None:
                pass

            def __enter__(self) -> "DummyRedis.Pipeline":
                return self

            def __exit__(self, exc_type, exc, tb) -> None:
                pass

        def pipeline(self) -> "DummyRedis.Pipeline":
            return DummyRedis.Pipeline(self)

    dummy = DummyRedis()
    # Reuse the dummy Redis client
    monkeypatch.setattr(modules_f4, "make_redis_client", lambda: dummy)

    monkeypatch.setattr(search_index, "get_all_pending_jobs", fake_get_jobs)
    monkeypatch.setattr(search_index, "add_or_update_chunk_documents", fake_add_chunks)
    monkeypatch.setattr(modules_f4, "update_doc_from_module", fake_update_doc)
    monkeypatch.setattr(
        search_index,
        "delete_chunk_docs_by_file_id_and_module",
        fake_delete,
    )
    monkeypatch.setattr(search_index, "wait_for_meili_idle", fake_wait)
    modules_f4.module_values = []

    result = asyncio.run(modules_f4.service_module_queue("mod", dummy))
    asyncio.run(modules_f4.process_done_queue(dummy))
    asyncio.run(modules_f4.process_done_queue(dummy))

    assert result is True
    assert recorded["lpop"]
    assert recorded["chunks"][0]["module"] == "mod"
    assert recorded["updated"]["id"] == doc["id"]


def test_service_module_queue_handles_update_only(monkeypatch):
    import importlib

    from features.F4 import modules as modules_f4
    from features.F2 import search_index

    importlib.reload(modules_f4)
    importlib.reload(search_index)

    doc = {"id": "file2", "mtime": 1.0, "paths": {"b.txt": 1.0}, "next": ""}

    async def fake_get_jobs(name):
        return [doc]

    recorded = {}

    async def fake_update_doc(d):
        recorded["updated"] = d

    class DummyRedis:
        def __init__(self):
            self.storage = {
                "mod:check": [],
                "mod:run": [],
                "modules:done": [json.dumps({"module": "mod", "document": doc})],
                "mod:check:processing": {},
                "mod:run:processing": {},
                "timeouts": {},
            }

        def rpush(self, key, val):
            if key.endswith(":check") or key.endswith(":run"):
                self.storage.setdefault(key, []).append(val)
            else:
                recorded["pushed"] = val

        def lpop(self, key):
            recorded["lpop"] = True
            if self.storage[key]:
                return self.storage[key].pop(0)
            return None

        def zrangebyscore(self, key, _min, _max):
            return []

        def lrange(self, key, _start, _end):
            return list(self.storage.get(key, []))

        def zrange(self, key, _start, _end):
            return list(self.storage.get(key, []))

        def zrem(self, key, member):
            pass

    dummy = DummyRedis()
    monkeypatch.setattr(modules_f4, "make_redis_client", lambda: dummy)

    monkeypatch.setattr(search_index, "get_all_pending_jobs", fake_get_jobs)
    monkeypatch.setattr(modules_f4, "update_doc_from_module", fake_update_doc)
    monkeypatch.setattr(
        search_index,
        "add_or_update_chunk_documents",
        lambda docs: recorded.setdefault("chunks", docs),
    )

    async def dummy_wait():
        recorded["waited"] = True

    monkeypatch.setattr(search_index, "wait_for_meili_idle", dummy_wait)
    modules_f4.module_values = []

    result = asyncio.run(modules_f4.service_module_queue("mod", dummy))
    asyncio.run(modules_f4.process_done_queue(dummy))

    assert result is True
    assert recorded.get("chunks") is None
    assert recorded["updated"]["id"] == doc["id"]
    assert recorded["lpop"]


def test_service_module_queue_processes_content(monkeypatch):
    import importlib

    from features.F4 import modules as modules_f4
    from features.F2 import search_index
    from features.F5 import chunking

    importlib.reload(modules_f4)
    importlib.reload(search_index)
    importlib.reload(chunking)

    doc = {
        "id": "file3",
        "mtime": 1.0,
        "paths": {"c.txt": 1.0},
        "next": "",
    }

    async def fake_get_jobs(name):
        return [doc]

    recorded = {}

    async def fake_update_doc(d):
        recorded["updated"] = d

    async def fake_chunks(docs):
        recorded["chunks"] = docs

    async def fake_delete(fid, mod):
        recorded["deleted"] = (fid, mod)

    class DummyRedis:
        def __init__(self):
            self.storage = {
                "mod:check": [],
                "mod:run": [],
                "modules:done": [
                    json.dumps(
                        {"module": "mod", "document": doc, "content": "hello world"}
                    )
                ],
                "mod:check:processing": {},
                "mod:run:processing": {},
                "timeouts": {},
            }

        def rpush(self, key, val):
            if key.endswith(":check") or key.endswith(":run"):
                self.storage.setdefault(key, []).append(val)

        def lpop(self, key):
            if self.storage[key]:
                return self.storage[key].pop(0)
            return None

        def zrangebyscore(self, key, _min, _max):
            return []

        def lrange(self, key, _start, _end):
            return list(self.storage.get(key, []))

        def zrange(self, key, _start, _end):
            return list(self.storage.get(key, []))

        def zrem(self, key, member):
            pass

    dummy = DummyRedis()
    monkeypatch.setattr(modules_f4, "make_redis_client", lambda: dummy)

    monkeypatch.setattr(search_index, "get_all_pending_jobs", fake_get_jobs)
    monkeypatch.setattr(modules_f4, "update_doc_from_module", fake_update_doc)
    monkeypatch.setattr(search_index, "add_or_update_chunk_documents", fake_chunks)
    monkeypatch.setattr(
        search_index,
        "delete_chunk_docs_by_file_id_and_module",
        fake_delete,
    )
    monkeypatch.setattr(search_index, "wait_for_meili_idle", lambda: None)
    modules_f4.module_values = []

    result = asyncio.run(modules_f4.service_module_queue("mod", dummy))
    asyncio.run(modules_f4.process_done_queue(dummy))

    assert result is True
    assert recorded.get("deleted") == ("file3", "mod")
    assert recorded["chunks"][0]["module"] == "mod"
    assert recorded["updated"]["id"] == doc["id"]
    assert "mod.content" not in recorded["updated"]


def test_sync_content_files_generates_chunks(monkeypatch, tmp_path):
    import importlib

    monkeypatch.setenv("BY_ID_DIRECTORY", str(tmp_path / "meta"))
    import features.F5.chunking as chunking
    from features.F4 import modules as modules_f4

    importlib.reload(chunking)
    importlib.reload(modules_f4)
    monkeypatch.setattr(
        chunking.metadata_store,
        "by_id_directory",
        lambda: Path(tmp_path / "meta" / "by-id"),
    )

    doc = {"id": "file4", "paths": {"d.txt": 1.0}, "next": ""}
    docs = {"file4": doc}
    mod_dir = Path(tmp_path / "meta" / "by-id" / "file4" / "mod")
    mod_dir.mkdir(parents=True)
    (mod_dir / "content.json").write_text("x")

    recorded = {}

    async def fake_add_content_chunks(document, module):
        recorded["chunks"] = True

    async def fake_update(docu):
        recorded["updated"] = docu

    monkeypatch.setattr(chunking, "add_content_chunks", fake_add_content_chunks)
    monkeypatch.setattr(modules_f4, "update_doc_from_module", fake_update)

    asyncio.run(chunking.sync_content_files(docs))

    assert recorded.get("chunks")
    assert recorded["updated"]["id"] == "file4"
    assert "mod.content" not in recorded["updated"]
