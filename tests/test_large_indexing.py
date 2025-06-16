import asyncio
import json
import os
import subprocess
import time
import threading
from contextlib import contextmanager
import sys
from pathlib import Path
from xmlrpc.server import SimpleXMLRPCServer
from xmlrpc.client import ServerProxy

import httpx
import importlib
import pytest
import xxhash

@contextmanager
def meilisearch_server(tmp_path, port):
    if os.environ.get("EXTERNAL_MEILISEARCH"):
        host = os.environ.get("MEILISEARCH_HOST", f"http://127.0.0.1:{port}")
        for _ in range(30):
            try:
                if httpx.get(f"{host}/health").status_code == 200:
                    break
            except Exception:
                time.sleep(0.5)
        else:
            raise RuntimeError("Meilisearch failed to start")
        yield
        return

    proc = subprocess.Popen(
        ["meilisearch", "--db-path", str(tmp_path), "--http-addr", f"127.0.0.1:{port}"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.STDOUT,
    )
    for _ in range(30):
        try:
            if httpx.get(f"http://127.0.0.1:{port}/health").status_code == 200:
                break
        except Exception:
            time.sleep(0.5)
    else:
        proc.terminate()
        proc.wait()
        raise RuntimeError("Meilisearch failed to start")
    try:
        yield
    finally:
        proc.terminate()
        proc.wait()

@contextmanager
def dummy_module_server(name, port, add_chunk=False):
    server = SimpleXMLRPCServer(("127.0.0.1", port), allow_none=True, logRequests=False)

    def hello():
        return json.dumps({
            "name": name,
            "version": 1,
            "filterable_attributes": [],
            "sortable_attributes": [],
        })

    def check(docs):
        docs = json.loads(docs)
        return json.dumps([d["id"] for d in docs])

    def load():
        return True

    def run(document_json):
        doc = json.loads(document_json)
        if add_chunk:
            chunk = {
                "id": f"{doc['id']}_chunk",
                "file_id": doc["id"],
                "module": name,
                "text": "hello",
            }
            return json.dumps({"document": doc, "chunk_docs": [chunk]})
        return json.dumps(doc)

    def unload():
        return True

    server.register_function(hello, "hello")
    server.register_function(check, "check")
    server.register_function(load, "load")
    server.register_function(run, "run")
    server.register_function(unload, "unload")

    thread = threading.Thread(target=server.serve_forever)
    thread.start()
    try:
        yield ServerProxy(f"http://127.0.0.1:{port}")
    finally:
        server.shutdown()
        thread.join()


def test_sync_and_run_many_files(tmp_path):
    async def run():
        files_dir = tmp_path / "files"
        files_dir.mkdir()
        file_count = 50
        for i in range(file_count):
            (files_dir / f"file{i}.txt").write_text(f"content {i}")
        metadata_dir = tmp_path / "metadata"
        log_dir = tmp_path / "logs"
        by_id = metadata_dir / "by-id"
        by_path = metadata_dir / "by-path"
        archive = tmp_path / "archive"
        for d in [metadata_dir, log_dir, archive]:
            d.mkdir(parents=True, exist_ok=True)
        os.environ["INDEX_DIRECTORY"] = str(files_dir)
        os.environ["METADATA_DIRECTORY"] = str(metadata_dir)
        os.environ["BY_ID_DIRECTORY"] = str(by_id)
        os.environ["BY_PATH_DIRECTORY"] = str(by_path)
        os.environ["ARCHIVE_DIRECTORY"] = str(archive)
        os.environ["LOGGING_DIRECTORY"] = str(log_dir)
        meili_port = 7720
        host = f"http://127.0.0.1:{meili_port}"
        with meilisearch_server(tmp_path / "meili", meili_port):
            os.environ["MEILISEARCH_HOST"] = host
            os.environ["MEILISEARCH_INDEX_NAME"] = "files_many"
            os.environ["MEILISEARCH_CHUNK_INDEX_NAME"] = "chunks_many"
            with dummy_module_server("mod1", 9020, add_chunk=True) as p1, dummy_module_server("mod2", 9021) as p2:
                os.environ["MODULES"] = "http://127.0.0.1:9020,http://127.0.0.1:9021"
                sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "packages"))
                import home_index.main as hi
                importlib.reload(hi)
                await hi.init_meili()
                hi.embed_texts = lambda texts: [[0.0] * hi.EMBED_DIM for _ in texts]

                docs = []
                for file_path in files_dir.iterdir():
                    stat = file_path.stat()
                    h = xxhash.xxh64(file_path.read_bytes()).hexdigest()
                    mtime = hi.truncate_mtime(stat.st_mtime)
                    docs.append(
                        {
                            "id": h,
                            "type": "text/plain",
                            "size": stat.st_size,
                            "paths": {file_path.name: mtime},
                            "copies": 1,
                            "mtime": mtime,
                            "next": "mod1",
                        }
                    )

                await hi.add_or_update_documents(docs)
                await hi.wait_for_meili_idle()
                hi.module_values = [
                    {"name": "mod1", "proxy": p1, "host": ""},
                    {"name": "mod2", "proxy": p2, "host": ""},
                ]
                await hi.run_module("mod1", p1)
                await hi.wait_for_meili_idle()
                await hi.run_module("mod2", p2)
                await hi.wait_for_meili_idle()
                total = await hi.get_document_count()
                assert total == file_count
                chunks = await hi.chunk_index.get_documents(limit=file_count)
                assert len(chunks.results) == file_count
    asyncio.run(run())
