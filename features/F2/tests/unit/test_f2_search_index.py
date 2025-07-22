import asyncio
import pytest


class DummyIndex:
    def __init__(self):
        self.updated = []
        self.deleted = []
        self.documents: list[dict] = []
        self.stats = type("Stats", (), {"number_of_documents": 3})()

    async def update_documents(self, docs):
        self.updated.append(list(docs))

    async def delete_documents(self, ids=None):
        self.deleted.append(list(ids))

    async def get_stats(self):
        return self.stats

    async def get_document(self, doc_id):
        return {"id": doc_id}

    async def get_documents(self, offset=0, limit=10, filter=None):
        docs = self.documents
        if filter:
            key, value = filter.split(" = ")
            docs = [d for d in docs if str(d.get(key)) == value]
        return type("Resp", (), {"results": docs[offset : offset + limit]})()


class DummyChunkIndex(DummyIndex):
    pass


class DummyClient:
    def __init__(self):
        self.calls = 0

    async def get_tasks(self):
        if self.calls == 0:
            self.calls += 1
            task = type("Task", (), {"status": "processing"})()
            return type("Resp", (), {"results": [task]})()
        return type("Resp", (), {"results": []})()


def setup(monkeypatch):
    import features.F2.search_index as si

    idx = DummyIndex()
    cidx = DummyChunkIndex()
    cli = DummyClient()
    monkeypatch.setattr(si, "index", idx)
    monkeypatch.setattr(si, "chunk_index", cidx)
    monkeypatch.setattr(si, "client", cli)
    monkeypatch.setattr(si, "MEILISEARCH_BATCH_SIZE", 2)
    return si, idx, cidx, cli


def test_add_and_delete_documents(monkeypatch):
    si, idx, _, _ = setup(monkeypatch)
    asyncio.run(si.add_or_update_documents([{"id": 1}, {"id": 2}, {"id": 3}]))
    assert idx.updated == [[{"id": 1}, {"id": 2}], [{"id": 3}]]
    asyncio.run(si.delete_docs_by_id(["a", "b", "c"]))
    assert idx.deleted == [["a", "b"], ["c"]]


def test_chunk_document_operations(monkeypatch):
    si, _, cidx, _ = setup(monkeypatch)
    asyncio.run(si.add_or_update_chunk_documents([{"id": 1}, {"id": 2}, {"id": 3}]))
    assert cidx.updated == [[{"id": 1}, {"id": 2}], [{"id": 3}]]
    asyncio.run(si.delete_chunk_docs_by_id(["x", "y", "z"]))
    assert cidx.deleted == [["x", "y"], ["z"]]


def test_delete_chunk_docs_by_file_id(monkeypatch):
    si, _, cidx, _ = setup(monkeypatch)
    cidx.documents = [
        {"id": "1", "file_id": "f1"},
        {"id": "2", "file_id": "f2"},
        {"id": "3", "file_id": "f1"},
    ]
    asyncio.run(si.delete_chunk_docs_by_file_ids(["f1"]))
    assert cidx.deleted == [["1", "3"]]


def test_delete_chunk_docs_by_file_id_and_module(monkeypatch):
    si, _, cidx, _ = setup(monkeypatch)
    cidx.documents = [
        {"id": "1", "file_id": "f1", "module": "m1"},
        {"id": "2", "file_id": "f1", "module": "m2"},
    ]
    asyncio.run(si.delete_chunk_docs_by_file_id_and_module("f1", "m1"))
    assert cidx.deleted == [["1"]]


def test_getters(monkeypatch):
    si, idx, _, _ = setup(monkeypatch)
    idx.documents = [{"id": "1", "next": "run"}, {"id": "2", "next": "check"}]
    assert asyncio.run(si.get_document_count()) == 3
    assert asyncio.run(si.get_document("1")) == {"id": "1"}
    assert asyncio.run(si.get_all_documents()) == idx.documents
    assert asyncio.run(si.get_all_pending_jobs("run")) == [{"id": "1", "next": "run"}]


def test_wait_for_meili_idle(monkeypatch):
    si, _, _, cli = setup(monkeypatch)
    sleep_calls = []

    async def fake_sleep(_):
        sleep_calls.append(1)

    monkeypatch.setattr(si.asyncio, "sleep", fake_sleep)
    asyncio.run(si.wait_for_meili_idle())
    assert sleep_calls


def test_errors_when_not_initialised(monkeypatch):
    import features.F2.search_index as si

    monkeypatch.setattr(si, "index", None)
    with pytest.raises(RuntimeError):
        asyncio.run(si.add_or_update_documents([]))
    monkeypatch.setattr(si, "chunk_index", None)
    with pytest.raises(RuntimeError):
        asyncio.run(si.add_or_update_chunk_documents([]))
    monkeypatch.setattr(si, "client", None)
    with pytest.raises(RuntimeError):
        asyncio.run(si.wait_for_meili_idle())
