import asyncio
import json


def test_service_module_queue_processes_chunk_docs(monkeypatch):
    import importlib
    import main as hi

    importlib.reload(hi)

    doc = {"id": "file1", "mtime": 1.0, "paths": {"a.txt": 1.0}, "next": ""}
    chunk = {"id": "chunk1", "text": "hello"}

    async def fake_get_jobs(name):
        return [doc]

    recorded = {}

    async def fake_add_chunks(docs):
        recorded["chunks"] = docs

    async def fake_update_doc(d):
        recorded["updated"] = d

    async def fake_wait():
        recorded["wait"] = True

    class DummyRedis:
        def __init__(self):
            self.storage = {
                "mod:check": [],
                "mod:run": [],
                "modules:done": [
                    json.dumps(
                        {"module": "mod", "document": doc, "chunk_docs": [chunk]}
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
    monkeypatch.setattr(hi.modules_f4, "make_redis_client", lambda: dummy)

    monkeypatch.setattr(hi, "get_all_pending_jobs", fake_get_jobs)
    monkeypatch.setattr(hi, "add_or_update_chunk_documents", fake_add_chunks)
    monkeypatch.setattr(hi, "update_doc_from_module", fake_update_doc)
    monkeypatch.setattr(hi, "wait_for_meili_idle", fake_wait)
    hi.module_values = []

    result = asyncio.run(hi.service_module_queue("mod", dummy))
    asyncio.run(hi.modules_f4.process_done_queue(dummy, hi))
    asyncio.run(hi.modules_f4.process_done_queue(dummy, hi))

    assert result is True
    assert recorded["lpop"]
    assert "_vector" not in recorded["chunks"][0]
    assert recorded["updated"]["id"] == doc["id"]


def test_service_module_queue_handles_update_only(monkeypatch):
    import importlib
    import main as hi

    importlib.reload(hi)

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
    monkeypatch.setattr(hi.modules_f4, "make_redis_client", lambda: dummy)

    monkeypatch.setattr(hi, "get_all_pending_jobs", fake_get_jobs)
    monkeypatch.setattr(hi, "update_doc_from_module", fake_update_doc)
    monkeypatch.setattr(
        hi,
        "add_or_update_chunk_documents",
        lambda docs: recorded.setdefault("chunks", docs),
    )

    async def dummy_wait():
        recorded["waited"] = True

    monkeypatch.setattr(hi, "wait_for_meili_idle", dummy_wait)
    hi.module_values = []

    result = asyncio.run(hi.service_module_queue("mod", dummy))
    asyncio.run(hi.modules_f4.process_done_queue(dummy, hi))

    assert result is True
    assert recorded.get("chunks") is None
    assert recorded["updated"]["id"] == doc["id"]
    assert recorded["lpop"]
