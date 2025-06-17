import json
import os
import time
import multiprocessing
from xmlrpc.client import ServerProxy

import pytest

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "packages"))
import fake_module


def start_server(port):
    fake_module.start(port)


def wait_for_server(port, timeout=20):
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            ServerProxy(f"http://127.0.0.1:{port}").hello()
            return
        except Exception:
            time.sleep(0.1)
    raise RuntimeError("server did not start")


def test_modules_communicate_via_xml_rpc(tmp_path):
    port = 9050
    files_dir = tmp_path / "files"
    meta_dir = tmp_path / "meta"
    by_id = meta_dir / "by-id"
    for d in (files_dir, meta_dir, by_id):
        d.mkdir(parents=True, exist_ok=True)
    os.environ["FILES_DIRECTORY"] = str(files_dir)
    os.environ["METADATA_DIRECTORY"] = str(meta_dir)
    os.environ["BY_ID_DIRECTORY"] = str(by_id)
    os.environ["LOGGING_DIRECTORY"] = str(tmp_path / "logs")
    proc = multiprocessing.Process(target=start_server, args=(port,), daemon=True)
    proc.start()
    try:
        wait_for_server(port)
        proxy = ServerProxy(f"http://127.0.0.1:{port}")

        proxy.load()

        hello = json.loads(proxy.hello())
        assert hello["name"] == fake_module.NAME
        assert hello["version"] == fake_module.VERSION

        docs = json.dumps([json.loads(open('docs/sample_document.json').read())])
        checked = json.loads(proxy.check(docs))
        assert checked == ["example-file"]

        doc = json.loads(open('docs/sample_document.json').read())
        result = json.loads(proxy.run(json.dumps(doc)))
        assert result["document"]["id"] == doc["id"]
        assert result["chunk_docs"][0]["module"] == fake_module.NAME

        proxy.unload()
    finally:
        proc.terminate()
        proc.join()
