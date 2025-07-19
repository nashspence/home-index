import asyncio


def _setup(monkeypatch, tmp_path):
    monkeypatch.setenv("BY_ID_DIRECTORY", str(tmp_path))
    import features.F5.chunking as chunking
    import features.F2.search_index as search_index
    import importlib

    importlib.reload(chunking)
    importlib.reload(search_index)
    return chunking, search_index


def test_add_content_chunks_writes_and_indexes(monkeypatch, tmp_path):
    chunking, search_index = _setup(monkeypatch, tmp_path)
    monkeypatch.setattr(chunking.metadata_store, "by_id_directory", lambda: tmp_path)

    recorded = {}

    async def fake_delete(file_id, module):
        recorded["delete"] = (file_id, module)

    async def fake_add(docs):
        recorded["add"] = docs

    monkeypatch.setattr(
        search_index, "delete_chunk_docs_by_file_id_and_module", fake_delete
    )
    monkeypatch.setattr(search_index, "add_or_update_chunk_documents", fake_add)
    monkeypatch.setattr(
        chunking, "build_chunk_docs_from_content", lambda *a, **k: [{"id": "x"}]
    )
    monkeypatch.setattr(
        chunking.chunk_utils,
        "write_chunk_docs",
        lambda p, d: recorded.setdefault("write", p),
    )

    asyncio.run(
        chunking.add_content_chunks({"id": "f", "mtime": 1.0}, "mod", content="hi")
    )

    assert recorded["delete"] == ("f", "mod")
    assert recorded["add"] == [{"id": "x"}]
    assert recorded["write"] == tmp_path / "f" / "mod"
    assert (tmp_path / "f" / "mod" / "content.json").exists()


def test_add_content_chunks_no_content_skips(monkeypatch, tmp_path):
    chunking, search_index = _setup(monkeypatch, tmp_path)
    monkeypatch.setattr(chunking.metadata_store, "by_id_directory", lambda: tmp_path)

    recorded = {}

    async def fake_delete(*_args):
        recorded["delete"] = True

    async def fake_add(*_args):
        recorded["add"] = True

    monkeypatch.setattr(
        search_index, "delete_chunk_docs_by_file_id_and_module", fake_delete
    )
    monkeypatch.setattr(search_index, "add_or_update_chunk_documents", fake_add)

    asyncio.run(chunking.add_content_chunks({"id": "f"}, "mod"))

    assert "delete" not in recorded
    assert "add" not in recorded


def test_add_content_chunks_reads_existing_content(monkeypatch, tmp_path):
    chunking, search_index = _setup(monkeypatch, tmp_path)
    monkeypatch.setattr(chunking.metadata_store, "by_id_directory", lambda: tmp_path)

    (tmp_path / "f" / "mod").mkdir(parents=True)
    (tmp_path / "f" / "mod" / "content.json").write_text('"hi"')

    recorded = {}

    async def fake_delete(file_id, module):
        recorded["delete"] = (file_id, module)

    async def fake_add(docs):
        recorded["add"] = docs

    monkeypatch.setattr(
        search_index, "delete_chunk_docs_by_file_id_and_module", fake_delete
    )
    monkeypatch.setattr(search_index, "add_or_update_chunk_documents", fake_add)
    monkeypatch.setattr(
        chunking, "build_chunk_docs_from_content", lambda *a, **k: [{"id": "y"}]
    )
    monkeypatch.setattr(
        chunking.chunk_utils,
        "write_chunk_docs",
        lambda p, d: recorded.setdefault("write", p),
    )

    asyncio.run(chunking.add_content_chunks({"id": "f"}, "mod"))

    assert recorded["delete"] == ("f", "mod")
    assert recorded["add"] == [{"id": "y"}]
    assert recorded["write"] == tmp_path / "f" / "mod"
