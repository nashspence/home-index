import asyncio
import json


def test_run_module_processes_chunk_docs(monkeypatch):
    import importlib
    import home_index.main as hi

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

    class DummyProxy:
        def load(self):
            recorded["load"] = True

        def run(self, data):
            recorded["run"] = True
            return json.dumps({"document": doc, "chunk_docs": [chunk]})

        def unload(self):
            recorded["unload"] = True

    monkeypatch.setattr(hi, "get_all_pending_jobs", fake_get_jobs)
    monkeypatch.setattr(hi, "add_or_update_chunk_documents", fake_add_chunks)
    monkeypatch.setattr(hi, "update_doc_from_module", fake_update_doc)
    monkeypatch.setattr(
        hi, "embed_texts", lambda texts: [[0.0] * hi.EMBED_DIM for _ in texts]
    )
    monkeypatch.setattr(hi, "wait_for_meili_idle", fake_wait)
    hi.module_values = []

    result = asyncio.run(hi.run_module("mod", DummyProxy()))

    assert result is False
    assert recorded["load"]
    assert recorded["unload"]
    assert recorded["chunks"][0]["_vector"] == [0.0] * hi.EMBED_DIM
    assert recorded["updated"]["id"] == doc["id"]


def test_run_module_handles_update_only(monkeypatch):
    import importlib
    import home_index.main as hi

    importlib.reload(hi)

    doc = {"id": "file2", "mtime": 1.0, "paths": {"b.txt": 1.0}, "next": ""}

    async def fake_get_jobs(name):
        return [doc]

    recorded = {}

    async def fake_update_doc(d):
        recorded["updated"] = d

    class DummyProxy:
        def load(self):
            recorded["load"] = True

        def run(self, data):
            recorded["run"] = True
            return json.dumps(doc)

        def unload(self):
            recorded["unload"] = True

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

    result = asyncio.run(hi.run_module("mod", DummyProxy()))

    assert result is False
    assert recorded.get("chunks") is None
    assert recorded["updated"]["id"] == doc["id"]
    assert recorded["load"] and recorded["unload"]
