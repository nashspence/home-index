import asyncio
import importlib
import json
from pathlib import Path
from typing import Any, Awaitable, Callable

from fastapi.testclient import TestClient  # noqa: E402
from features.F6 import api  # noqa: E402


def test_debounce_cancels_previous(monkeypatch):
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    cancelled = []

    class DummyHandle:
        def __init__(self) -> None:
            self.cancelled = False

        def cancel(self) -> None:
            self.cancelled = True
            cancelled.append(True)

    def fake_call_later(_delay: float, callback):
        callback()
        return DummyHandle()

    monkeypatch.setattr(loop, "call_later", fake_call_later)
    monkeypatch.setattr(asyncio, "create_task", lambda c: loop.create_task(c))

    api._debounce_handle = None
    called: list[str] = []

    async def coro1() -> None:
        called.append("one")

    async def coro2() -> None:
        called.append("two")

    api.debounce(lambda: coro1(), loop)
    loop.run_until_complete(asyncio.sleep(0))
    api.debounce(lambda: coro2(), loop)
    loop.run_until_complete(asyncio.sleep(0))
    loop.close()
    asyncio.set_event_loop(None)

    assert cancelled
    assert called == ["one", "two"]


def test_file_ops_endpoint_calls_debounce(monkeypatch):
    recorded: dict[str, Any] = {}

    async def fake_apply(ops: api.FileOps) -> None:
        recorded["ops"] = ops

    def fake_debounce(cf, _loop):
        recorded["coro"] = cf

    monkeypatch.setattr(api, "apply_ops", fake_apply)
    monkeypatch.setattr(api, "debounce", fake_debounce)

    with TestClient(api.app) as client:
        res = client.post("/fileops", json={"move": [{"src": "a", "dest": "b"}]})
        assert res.status_code == 202
        assert res.json() == {"status": "accepted"}

    loop = asyncio.new_event_loop()
    loop.run_until_complete(recorded["coro"]())
    loop.close()
    asyncio.set_event_loop(None)

    assert recorded["ops"].move[0].src == "a"
    assert recorded["ops"].move[0].dest == "b"


def test_ops_provider_methods(monkeypatch, tmp_path: Path):
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    recorded_ops: list[api.FileOps] = []
    recorded_cf: list[Callable[[], Awaitable[None]]] = []

    async def fake_apply(ops: api.FileOps) -> None:
        recorded_ops.append(ops)

    def fake_debounce(cf, _loop):
        recorded_cf.append(cf)

    monkeypatch.setattr(api, "apply_ops", fake_apply)
    monkeypatch.setattr(api, "debounce", fake_debounce)
    monkeypatch.setattr(api, "INDEX_DIRECTORY", tmp_path)

    provider = api.OpsProvider(tmp_path)

    async def gen():
        yield b"hi"

    loop.run_until_complete(provider.create("a.txt", gen()))
    loop.run_until_complete(recorded_cf.pop()())
    assert recorded_ops[-1].add[0].path == "a.txt"

    loop.run_until_complete(provider.move("a.txt", "b.txt"))
    loop.run_until_complete(recorded_cf.pop()())
    assert recorded_ops[-1].move[0].dest == "b.txt"

    loop.run_until_complete(provider.delete("b.txt"))
    loop.run_until_complete(recorded_cf.pop()())
    assert recorded_ops[-1].delete[0] == "b.txt"
    loop.close()
    asyncio.set_event_loop(None)


def test_apply_ops_add_move_delete(monkeypatch, tmp_path: Path):
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    import main as hi

    hi = importlib.reload(hi)

    index_dir = tmp_path / "index"
    meta_dir = tmp_path / "meta"
    by_id = meta_dir / "by-id"
    links = tmp_path / "links"
    index_dir.mkdir()
    by_id.mkdir(parents=True)
    links.mkdir()

    import features.F2.duplicate_finder as df
    import features.F2.metadata_store as metadata_store
    import features.F2.path_links as path_links
    import features.F3.archive as archive
    import features.F4.modules as modules_f4

    monkeypatch.setattr(api, "INDEX_DIRECTORY", index_dir)
    monkeypatch.setattr(df, "compute_hash", lambda p: "id1")
    monkeypatch.setattr(df, "truncate_mtime", lambda m: 1.0)
    monkeypatch.setattr(metadata_store, "by_id_directory", lambda: by_id)
    monkeypatch.setattr(path_links, "by_path_directory", lambda: links)

    monkeypatch.setattr(archive, "update_archive_flags", lambda d: None)
    monkeypatch.setattr(modules_f4, "set_next_modules", lambda d, **kw: None)

    added: dict[str, Any] = {}
    deleted: dict[str, Any] = {}

    async def add_docs(docs):
        added["docs"] = docs

    async def del_docs(ids):
        deleted["ids"] = ids

    async def del_chunks(ids):
        deleted["chunks"] = ids

    async def waited():
        deleted["waited"] = True

    monkeypatch.setattr(hi, "add_or_update_documents", add_docs)
    monkeypatch.setattr(hi, "delete_docs_by_id", del_docs)
    monkeypatch.setattr(hi, "delete_chunk_docs_by_file_ids", del_chunks)
    monkeypatch.setattr(hi, "wait_for_meili_idle", waited)
    monkeypatch.setattr(hi, "get_mime_type", lambda p: "text/plain")
    monkeypatch.setattr(hi, "CURRENT_VERSION", 1)

    tmp_file = tmp_path / "tmp"
    tmp_file.write_text("a")
    loop.run_until_complete(
        api.apply_ops(
            api.FileOps(add=[api.AddItem(path="a.txt", content_path=tmp_file)])
        )
    )
    assert (index_dir / "a.txt").exists()
    assert added["docs"][0]["id"] == "id1"

    doc_dir = by_id / "id1"
    loop.run_until_complete(
        api.apply_ops(api.FileOps(move=[api.MoveItem(src="a.txt", dest="b.txt")]))
    )
    assert (index_dir / "b.txt").exists()
    with open(doc_dir / "document.json") as fh:
        doc = json.load(fh)
    assert "b.txt" in doc["paths"]
    loop.run_until_complete(api.apply_ops(api.FileOps(delete=["b.txt"])))
    loop.close()
    asyncio.set_event_loop(None)
    assert deleted["ids"] == ["id1"]
    assert deleted["chunks"] == ["id1"]
    assert deleted["waited"]
