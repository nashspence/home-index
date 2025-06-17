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


@contextmanager
def meilisearch_server(tmp_path, port):
    if os.environ.get("EXTERNAL_MEILISEARCH"):
        # Wait for the external service to be ready
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
def dummy_module_server(port):
    server = SimpleXMLRPCServer(("127.0.0.1", port), allow_none=True, logRequests=False)

    def hello():
        return json.dumps(
            {
                "name": "dummy",
                "version": 1,
                "filterable_attributes": [],
                "sortable_attributes": [],
            }
        )

    def check(docs):
        docs = json.loads(docs)
        return json.dumps([d["id"] for d in docs])

    def load():
        return True

    def run(document_json):
        doc = json.loads(document_json)
        chunk = {
            "id": "chunk1",
            "file_id": doc["id"],
            "module": "dummy",
            "text": "hello",
        }
        return json.dumps({"document": doc, "chunk_docs": [chunk]})

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


@contextmanager
def dummy_module_server_plain(port):
    server = SimpleXMLRPCServer(("127.0.0.1", port), allow_none=True, logRequests=False)

    def hello():
        return json.dumps(
            {
                "name": "dummy",
                "version": 1,
                "filterable_attributes": [],
                "sortable_attributes": [],
            }
        )

    def check(docs):
        docs = json.loads(docs)
        return json.dumps([d["id"] for d in docs])

    def load():
        return True

    def run(document_json):
        doc = json.loads(document_json)
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


def test_modules_can_add_and_remove_chunk_data(tmp_path):
    async def run():
        meili_port = 7710
        host = os.environ.get("MEILISEARCH_HOST", f"http://127.0.0.1:{meili_port}")
        with meilisearch_server(tmp_path / "meili", meili_port):
            os.environ["MEILISEARCH_HOST"] = host
            os.environ["MEILISEARCH_INDEX_NAME"] = "files_test"
            os.environ["MEILISEARCH_CHUNK_INDEX_NAME"] = "chunks_test"
            os.environ["MODULES"] = ""
            index_dir = tmp_path / "index"
            meta_dir = tmp_path / "metadata"
            by_id = meta_dir / "by-id"
            by_path = meta_dir / "by-path"
            archive = tmp_path / "archive"
            log_dir = tmp_path / "logs"
            for d in [index_dir, meta_dir, by_id, by_path, archive, log_dir]:
                d.mkdir(parents=True, exist_ok=True)
            os.environ["INDEX_DIRECTORY"] = str(index_dir)
            os.environ["METADATA_DIRECTORY"] = str(meta_dir)
            os.environ["BY_ID_DIRECTORY"] = str(by_id)
            os.environ["BY_PATH_DIRECTORY"] = str(by_path)
            os.environ["ARCHIVE_DIRECTORY"] = str(archive)
            os.environ["LOGGING_DIRECTORY"] = str(log_dir)
            sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "packages"))
            import home_index.main as hi

            importlib.reload(hi)
            await hi.init_meili()

            hi.embed_texts = lambda texts: [[0.0] * hi.EMBED_DIM for _ in texts]

            doc = {
                "id": "file1",
                "type": "text/plain",
                "size": 1,
                "paths": {"foo/a.txt": 1.0},
                "copies": 1,
                "mtime": 1.0,
                "next": "dummy",
            }
            await hi.add_or_update_document(doc)
            await hi.wait_for_meili_idle()

            with dummy_module_server(9010) as proxy:
                hi.module_values = [{"name": "dummy", "proxy": proxy, "host": ""}]
                await hi.run_module("dummy", proxy)
                await hi.wait_for_meili_idle()

            chunk = await hi.chunk_index.get_document("chunk1")
            assert chunk["file_id"] == "file1"
            assert chunk["module"] == "dummy"
            assert chunk["text"] == "passage: hello"
            assert len(chunk["_vector"]) == hi.EMBED_DIM

            await hi.delete_docs_by_id(["file1"])
            await hi.delete_chunk_docs_by_file_ids(["file1"])
            await hi.wait_for_meili_idle()

            docs = await hi.chunk_index.get_documents()
            assert len(docs.results) == 0

    asyncio.run(run())


def test_modules_may_return_only_updated_documents(tmp_path):
    async def run():
        meili_port = 7711
        host = os.environ.get("MEILISEARCH_HOST", f"http://127.0.0.1:{meili_port}")
        with meilisearch_server(tmp_path / "meili", meili_port):
            os.environ["MEILISEARCH_HOST"] = host
            os.environ["MEILISEARCH_INDEX_NAME"] = "files_test2"
            os.environ["MEILISEARCH_CHUNK_INDEX_NAME"] = "chunks_test2"
            os.environ["MODULES"] = ""
            index_dir = tmp_path / "index"
            meta_dir = tmp_path / "metadata"
            by_id = meta_dir / "by-id"
            by_path = meta_dir / "by-path"
            archive = tmp_path / "archive"
            log_dir = tmp_path / "logs2"
            for d in [index_dir, meta_dir, by_id, by_path, archive, log_dir]:
                d.mkdir(parents=True, exist_ok=True)
            os.environ["INDEX_DIRECTORY"] = str(index_dir)
            os.environ["METADATA_DIRECTORY"] = str(meta_dir)
            os.environ["BY_ID_DIRECTORY"] = str(by_id)
            os.environ["BY_PATH_DIRECTORY"] = str(by_path)
            os.environ["ARCHIVE_DIRECTORY"] = str(archive)
            os.environ["LOGGING_DIRECTORY"] = str(log_dir)
            sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "packages"))
            import home_index.main as hi

            importlib.reload(hi)
            await hi.init_meili()

            doc = {
                "id": "file2",
                "type": "text/plain",
                "size": 1,
                "paths": {"b.txt": 1.0},
                "copies": 1,
                "mtime": 1.0,
                "next": "dummy",
            }
            await hi.add_or_update_document(doc)
            await hi.wait_for_meili_idle()

            with dummy_module_server_plain(9011) as proxy:
                hi.module_values = [{"name": "dummy", "proxy": proxy, "host": ""}]
                await hi.run_module("dummy", proxy)
                await hi.wait_for_meili_idle()

            docs = await hi.chunk_index.get_documents()
            assert len(docs.results) == 0

    asyncio.run(run())
