import json
from pathlib import Path


def test_add_paths_list_populates_and_sorts():
    import features.F2.metadata_store as ms

    doc = {"paths": {"b": 1.0, "a": 2.0}}
    ms._add_paths_list(doc)
    assert doc["paths_list"] == ["a", "b"]
    assert doc["version"] == 1


def test_write_doc_json_creates_directories(monkeypatch, tmp_path: Path):
    import features.F2.metadata_store as ms

    monkeypatch.setenv("METADATA_DIRECTORY", str(tmp_path / "meta"))
    monkeypatch.setenv("BY_ID_DIRECTORY", str(tmp_path / "meta" / "by-id"))
    doc = {"id": "x", "paths": {}}
    ms.write_doc_json(doc)
    target = tmp_path / "meta" / "by-id" / "x" / "document.json"
    assert target.exists()
    assert json.loads(target.read_text())["id"] == "x"
