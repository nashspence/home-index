import asyncio
import importlib
import json
from pathlib import Path
from typing import Any

import pytest


def _reload_modules(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    monkeypatch.setenv("MODULES", "")
    monkeypatch.setenv("HELLO_VERSIONS_FILE_PATH", str(tmp_path / "hv.json"))
    return importlib.reload(__import__("features.F4.modules", fromlist=["*"]))


def test_file_relpath_from_meili_doc(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    modules = _reload_modules(monkeypatch, tmp_path)
    doc = {"paths": {"a.txt": 1.0, "b.txt": 2.0}}
    assert modules.file_relpath_from_meili_doc(doc) == "a.txt"


def test_metadata_dir_relpath_from_doc_creates_directory(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("METADATA_DIRECTORY", str(tmp_path / "meta"))
    monkeypatch.setenv("BY_ID_DIRECTORY", str(tmp_path / "meta" / "by-id"))
    modules = _reload_modules(monkeypatch, tmp_path)
    doc = {"id": "123"}
    rel = modules.metadata_dir_relpath_from_doc("mod", doc)
    expected = Path("by-id") / "123" / "mod"
    assert rel == expected
    assert (tmp_path / "meta" / rel).is_dir()


def test_set_next_modules_assigns_module_names(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    modules = _reload_modules(monkeypatch, tmp_path)

    class Proxy1:
        def check(self, data: str) -> str:
            return json.dumps(["1"])

    class Proxy2:
        def check(self, data: str) -> str:
            return json.dumps(["2"])

    modules.module_values = [
        {"name": "m1", "proxy": Proxy1(), "host": "h1"},
        {"name": "m2", "proxy": Proxy2(), "host": "h2"},
    ]

    docs = {"1": {"id": "1", "next": ""}, "2": {"id": "2", "next": ""}}

    monkeypatch.setattr(modules, "retry_until_ready", lambda fn, msg, seconds=0: fn())
    monkeypatch.setattr(modules, "doc_is_online", lambda doc: True)

    modules.set_next_modules(docs)
    assert docs["1"]["next"] == "m1"
    assert docs["2"]["next"] == "m2"


def test_update_doc_from_module_updates_and_saves(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    modules = _reload_modules(monkeypatch, tmp_path)
    import main as hi

    importlib.reload(hi)

    class ProxyIgnore:
        def check(self, data: str) -> str:
            return json.dumps([])

    class ProxyClaim:
        def check(self, data: str) -> str:
            return json.dumps(["1"])

    modules.module_values = [
        {"name": "m1", "proxy": ProxyIgnore(), "host": "h1"},
        {"name": "m2", "proxy": ProxyClaim(), "host": "h2"},
    ]

    recorded: dict[str, Any] = {}

    async def fake_add(doc: dict[str, Any]) -> None:
        recorded["added"] = doc

    monkeypatch.setattr(hi, "add_or_update_document", fake_add)
    monkeypatch.setattr(
        modules, "update_archive_flags", lambda d: recorded.setdefault("flags", True)
    )
    monkeypatch.setattr(
        modules, "write_doc_json", lambda d: recorded.setdefault("written", True)
    )
    monkeypatch.setattr(modules, "retry_until_ready", lambda fn, msg, seconds=0: fn())

    doc = {"id": "1", "paths": {"a.txt": 1.0}, "next": "m1"}
    asyncio.run(modules.update_doc_from_module(doc))

    assert doc["next"] == "m2"
    assert recorded["added"]["id"] == "1"
    assert recorded.get("flags") and recorded.get("written")


def test_modules_state_round_trip(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    modules = _reload_modules(monkeypatch, tmp_path)
    modules.hello_versions = [["mod", 1]]
    modules.save_modules_state()
    assert modules.get_is_modules_changed() is False
    modules.hello_versions = [["mod", 2]]
    assert modules.get_is_modules_changed() is True
