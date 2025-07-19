import asyncio
import importlib
from pathlib import Path
from typing import Any

import pytest


def _reload_modules(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    monkeypatch.setenv("MODULES", "")
    monkeypatch.setenv("MODULES_CONFIG_FILE_PATH", str(tmp_path / "config.json"))
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

    modules.module_values = [
        {"name": "m1"},
        {"name": "m2"},
    ]
    modules.modules = {
        "m1": modules.module_values[0],
        "m2": modules.module_values[1],
    }

    docs = {"1": {"id": "1", "next": ""}, "2": {"id": "2", "next": ""}}

    monkeypatch.setattr(modules, "doc_is_online", lambda doc: True)

    modules.set_next_modules(docs)
    assert docs["1"]["next"] == "m1"
    assert docs["2"]["next"] == "m1"


def test_set_next_modules_force_offline(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    modules = _reload_modules(monkeypatch, tmp_path)

    modules.module_values = [
        {"name": "m1"},
    ]
    modules.modules = {"m1": modules.module_values[0]}

    docs = {"1": {"id": "1", "next": ""}}

    monkeypatch.setattr(modules, "doc_is_online", lambda doc: False)

    modules.set_next_modules(docs, force_offline=True)
    assert docs["1"]["next"] == "m1"


def test_update_doc_from_module_updates_and_saves(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    modules = _reload_modules(monkeypatch, tmp_path)
    from features.F2 import search_index

    importlib.reload(search_index)

    modules.module_values = [
        {"name": "m1"},
        {"name": "m2"},
    ]
    modules.modules = {
        "m1": modules.module_values[0],
        "m2": modules.module_values[1],
    }

    recorded: dict[str, Any] = {}

    async def fake_add(doc: dict[str, Any]) -> None:
        recorded["added"] = doc

    monkeypatch.setattr(
        search_index, "add_or_update_documents", lambda docs: fake_add(docs[0])
    )
    monkeypatch.setattr(
        modules, "update_archive_flags", lambda d: recorded.setdefault("flags", True)
    )
    monkeypatch.setattr(
        modules, "write_doc_json", lambda d: recorded.setdefault("written", True)
    )

    doc = {"id": "1", "paths": {"a.txt": 1.0}, "next": "m1"}
    asyncio.run(modules.update_doc_from_module(doc))

    assert doc["next"] == "m2"
    assert recorded["added"]["id"] == "1"
    assert recorded.get("flags") and recorded.get("written")


def test_modules_state_round_trip(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    modules = _reload_modules(monkeypatch, tmp_path)
    modules.module_configs = [{"name": "mod"}]
    modules.save_modules_state()
    assert modules.get_is_modules_changed() is False
    modules.module_configs = [{"name": "mod2"}]
    assert modules.get_is_modules_changed() is True
