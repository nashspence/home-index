import asyncio


def test_update_meilisearch_adds_and_deletes_documents(monkeypatch):
    import importlib
    import main as hi

    importlib.reload(hi)

    upsert = {"doc1": {"id": "doc1"}}
    files = {"doc1": {"id": "doc1"}}

    recorded = {"deleted": [], "deleted_chunks": []}

    async def fake_get_all_documents():
        return []

    async def fake_delete(ids):
        recorded["deleted"] = ids

    async def fake_delete_chunks(ids):
        recorded["deleted_chunks"] = ids

    async def fake_add(docs):
        recorded["added"] = docs

    async def fake_count():
        recorded["count"] = True
        return 1

    monkeypatch.setattr(hi, "get_all_documents", fake_get_all_documents)
    monkeypatch.setattr(hi, "delete_docs_by_id", fake_delete)
    monkeypatch.setattr(hi, "delete_chunk_docs_by_file_ids", fake_delete_chunks)
    monkeypatch.setattr(hi, "add_or_update_documents", fake_add)
    monkeypatch.setattr(hi, "get_document_count", fake_count)

    async def dummy_wait():
        recorded["waited"] = True

    monkeypatch.setattr(hi, "wait_for_meili_idle", dummy_wait)

    asyncio.run(hi.update_meilisearch(upsert, files))

    assert recorded["added"] == [{"id": "doc1"}]
    assert recorded["deleted"] == []
    assert recorded["deleted_chunks"] == []
    assert recorded["count"]
