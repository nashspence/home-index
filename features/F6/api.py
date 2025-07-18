"""
home_share.py – mountable WebDAV endpoint + JSON /fileops API
-------------------------------------------------------------

  pip install fastapi asgiwebdav[async_filesystem] uvicorn aiofiles
  # optional if you ever switch to WSGI:
  # pip install wsgidav

Run:
  python home_share.py        # 0.0.0.0:8000

Mount (macOS / Finder):
  ⌘K  →  https://server:8000/dav

Mount (Linux):
  sudo mount -t davfs https://server:8000/dav /mnt/remote
"""

from __future__ import annotations

import asyncio
import importlib
import json
import os
import shutil
import sys
import tempfile
from pathlib import Path
from typing import Any, AsyncIterable, Awaitable, Callable, Dict, List, cast

from fastapi import FastAPI, Request, status
from pydantic import BaseModel

try:
    from asgi_webdav import WebDavApp, FileSystemProvider
    import aiofiles as _aiofiles
except Exception:  # pragma: no cover - optional deps may be missing
    _aiofiles = None

    class _DummyProvider:
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            pass

    class _DummyApp:
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            pass

    FileSystemProvider = cast(Any, _DummyProvider)
    WebDavApp = cast(Any, _DummyApp)

aiofiles: Any | None = _aiofiles

# ------------------------------------------------------------------------
# Configuration
# ------------------------------------------------------------------------
API_PORT = int(os.getenv("FILE_API_PORT", 8000))
INDEX_DIRECTORY = Path(os.getenv("INDEX_DIRECTORY", "/files")).resolve()
INDEX_DIRECTORY.mkdir(parents=True, exist_ok=True)

# How long to wait after the **last** mutating op before kicking heavy work
DEBOUNCE_SECONDS = 2.0

app = FastAPI(title="Home‑Share API")


# ------------------------------------------------------------------------
# Pydantic models – unchanged from your original code
# ------------------------------------------------------------------------
class AddItem(BaseModel):  # type: ignore[misc]
    path: str
    content_path: Path  # now we stream to a temp‑file and pass its path


class MoveItem(BaseModel):  # type: ignore[misc]
    src: str
    dest: str


class FileOps(BaseModel):  # type: ignore[misc]
    add: List[AddItem] = []
    move: List[MoveItem] = []
    delete: List[str] = []


def _get_hi() -> Any:
    """Return the running ``main`` module without importing at type-check time."""
    hi = sys.modules.get("main") or sys.modules.get("__main__")
    if hi is None:
        hi = importlib.import_module("main")
    return hi


# ------------------------------------------------------------------------
# Heavy lifting – lifted verbatim from your old /fileops route,
# with tiny tweaks for streamed uploads
# ------------------------------------------------------------------------
async def apply_ops(ops: FileOps) -> None:
    """
    Mutate files on disk *and* update metadata / Meilisearch.
    The body is 99 % your original code – only the file‑write section
    changed to accept a temp file path instead of base64.
    """
    # Lazy import to avoid cycles and keep mypy happy
    hi = cast(Any, _get_hi())
    from features.F2 import duplicate_finder, metadata_store, path_links
    from features.F3 import archive
    from features.F4 import modules as modules_f4

    docs_to_upsert: Dict[str, Dict[str, Any]] = {}
    ids_to_delete: List[str] = []

    # ---------- ADD -----------------------------------------------------
    for item in ops.add:
        target = INDEX_DIRECTORY / item.path
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(item.content_path, target)

        stat = target.stat()
        file_id = duplicate_finder.compute_hash(target)
        mtime = duplicate_finder.truncate_mtime(stat.st_mtime)
        doc = {
            "id": file_id,
            "paths": {item.path: mtime},
            "paths_list": [item.path],
            "mtime": mtime,
            "size": stat.st_size,
            "type": hi.get_mime_type(target),
            "copies": 1,
            "version": hi.CURRENT_VERSION,
            "next": "",
        }
        archive.update_archive_flags(doc)
        modules_f4.set_next_modules(
            {file_id: doc}, force_offline=modules_f4.is_modules_changed
        )
        metadata_store.write_doc_json(doc)
        path_links.link_path(item.path, file_id)
        docs_to_upsert[file_id] = doc

    # ---------- MOVE ----------------------------------------------------
    for item in ops.move:
        src = INDEX_DIRECTORY / item.src
        dest = INDEX_DIRECTORY / item.dest
        if not src.exists():
            continue
        dest.parent.mkdir(parents=True, exist_ok=True)
        src.rename(dest)
        link = path_links.by_path_directory() / item.src
        if not link.is_symlink():
            continue
        doc_id = link.resolve().name
        path_links.unlink_path(item.src)
        path_links.link_path(item.dest, doc_id)
        doc_file = metadata_store.by_id_directory() / doc_id / "document.json"
        if not doc_file.exists():
            continue
        with open(doc_file) as fh:
            doc_data: Dict[str, Any] = json.load(fh)
        mtime = duplicate_finder.truncate_mtime(dest.stat().st_mtime)
        doc_data["paths"].pop(item.src, None)
        doc_data["paths"][item.dest] = mtime
        doc_data["paths_list"] = sorted(doc_data["paths"].keys())
        doc_data["mtime"] = max(doc_data["paths"].values())
        doc_data["copies"] = len(doc_data["paths"])
        doc_data["type"] = hi.get_mime_type(dest)
        doc_data["version"] = hi.CURRENT_VERSION
        archive.update_archive_flags(doc_data)
        modules_f4.set_next_modules(
            {doc_id: doc_data}, force_offline=modules_f4.is_modules_changed
        )
        metadata_store.write_doc_json(doc_data)
        docs_to_upsert[doc_id] = doc_data

    # ---------- DELETE --------------------------------------------------
    for rel in ops.delete:
        path = INDEX_DIRECTORY / rel
        if path.exists():
            if path.is_dir():
                shutil.rmtree(path)
            else:
                path.unlink()
        link = path_links.by_path_directory() / rel
        if not link.is_symlink():
            continue
        doc_id = link.resolve().name
        path_links.unlink_path(rel)
        doc_file = metadata_store.by_id_directory() / doc_id / "document.json"
        if not doc_file.exists():
            continue
        with open(doc_file) as fh:
            doc_data_del: Dict[str, Any] = json.load(fh)
        doc_data_del["paths"].pop(rel, None)
        if not doc_data_del["paths"]:
            shutil.rmtree(doc_file.parent)
            ids_to_delete.append(doc_id)
        else:
            doc_data_del["paths_list"] = sorted(doc_data_del["paths"].keys())
            doc_data_del["mtime"] = max(doc_data_del["paths"].values())
            doc_data_del["copies"] = len(doc_data_del["paths"])
            archive.update_archive_flags(doc_data_del)
            modules_f4.set_next_modules(
                {doc_id: doc_data_del}, force_offline=modules_f4.is_modules_changed
            )
            metadata_store.write_doc_json(doc_data_del)
            docs_to_upsert[doc_id] = doc_data_del

    # ---------- SEARCH INDEX -------------------------------------------
    if docs_to_upsert:
        await hi.add_or_update_documents(list(docs_to_upsert.values()))
    if ids_to_delete:
        await hi.delete_docs_by_id(ids_to_delete)
        await hi.delete_chunk_docs_by_file_ids(ids_to_delete)
    if docs_to_upsert or ids_to_delete:
        await hi.wait_for_meili_idle()


# ------------------------------------------------------------------------
# Debounce helper – one task shared by all requests
# ------------------------------------------------------------------------
_debounce_lock = asyncio.Lock()
_debounce_handle: asyncio.TimerHandle | None = None


def debounce(
    coro_factory: Callable[[], Awaitable[None]], loop: asyncio.AbstractEventLoop
) -> None:
    global _debounce_handle

    async def runner() -> None:
        await coro_factory()

    async def schedule() -> None:
        global _debounce_handle
        async with _debounce_lock:
            if _debounce_handle:
                _debounce_handle.cancel()
            _debounce_handle = loop.call_later(
                DEBOUNCE_SECONDS, lambda: asyncio.create_task(runner())
            )

    asyncio.create_task(schedule())


# ------------------------------------------------------------------------
# FastAPI JSON endpoint – useful for tests / scripting
# ------------------------------------------------------------------------
@app.post("/fileops", status_code=status.HTTP_202_ACCEPTED)  # type: ignore[misc]
async def file_ops_endpoint(ops: FileOps, request: Request) -> Dict[str, str]:
    loop = asyncio.get_running_loop()
    debounce(lambda: apply_ops(ops), loop)
    return {"status": "accepted"}


# ------------------------------------------------------------------------
# WebDAV provider – translate DAV verbs → FileOps objects  --------------
# ------------------------------------------------------------------------
class OpsProvider(FileSystemProvider):  # type: ignore[misc]
    """
    We inherit normal read‑only behaviour but override create/move/delete so
    that every mutating FS action is funneled into `apply_ops()` (via debounce).
    """

    async def create(
        self, rel_path: str, data_iter: AsyncIterable[bytes], **kw: Any
    ) -> None:
        # Stream body to a temp‑file on disk
        fd, tmp = tempfile.mkstemp(dir=str(INDEX_DIRECTORY))
        os.close(fd)
        if aiofiles:
            async with aiofiles.open(tmp, "wb") as tmp_fh:
                async for chunk in data_iter:
                    await tmp_fh.write(chunk)
        else:
            with open(tmp, "wb") as tmp_fh:
                async for chunk in data_iter:
                    tmp_fh.write(chunk)

        ops = FileOps(add=[AddItem(path=rel_path, content_path=Path(tmp))])
        debounce(lambda: apply_ops(ops), asyncio.get_running_loop())

    async def move(self, src: str, dst: str, **kw: Any) -> None:
        ops = FileOps(move=[MoveItem(src=src, dest=dst)])
        debounce(lambda: apply_ops(ops), asyncio.get_running_loop())

    async def delete(self, rel_path: str, **kw: Any) -> None:
        ops = FileOps(delete=[rel_path])
        debounce(lambda: apply_ops(ops), asyncio.get_running_loop())


# Mount DAV at /dav
provider = OpsProvider(INDEX_DIRECTORY)
app.mount("/dav", WebDavApp(provider=provider))

# ------------------------------------------------------------------------
# Optional: WSGI variant – uncomment if you move to Gunicorn + WsgiDAV
# ------------------------------------------------------------------------
"""
from wsgidav.wsgidav_app import WsgiDAVApp
from wsgidav.fs_dav_provider import FilesystemProvider as WsgiFS

def make_wsgi_app() -> WsgiDAVApp:
    config = {
        "provider_mapping": {"/": WsgiFS(str(INDEX_DIRECTORY))},
        "simple_dc": {"user_mapping": {"*": True}},  # open share
        "verbose": 1,
        "middleware_stack": ["wsgidav.dir_browser.DirBrowser"],
    }
    return WsgiDAVApp(config)
"""

# ------------------------------------------------------------------------
# Main entrypoint
# ------------------------------------------------------------------------
if __name__ == "__main__":
    import uvicorn

    uvicorn.run("home_share:app", host="0.0.0.0", port=API_PORT, reload=False)
