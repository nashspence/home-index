import importlib
from pathlib import Path

import pytest


def test_segments_with_headers_convert_to_chunk_documents_referencing_the_source_file():
    from features.f5.chunk_utils import segments_to_chunk_docs

    segments = [
        {"header": {"speaker": "A"}, "doc": {"text": "hello"}},
        {"doc": {"text": "bye"}},
    ]

    docs = segments_to_chunk_docs(segments, "file1", module_name="mod")
    assert docs[0]["id"] == "mod_file1_0"
    assert docs[0]["file_id"] == "file1"
    assert docs[0]["index"] == 0
    assert docs[0]["text"].startswith("[speaker: A]\n")
    assert docs[1]["id"] == "mod_file1_1"
    assert docs[1]["file_id"] == "file1"
    assert docs[1]["index"] == 1


def test_tokentextsplitter_divides_chunk_text_into_smaller_documents():
    from features.f5.chunk_utils import split_chunk_docs

    chunks = [{"id": "c1", "file_id": "f", "module": "m", "text": "a b c d"}]
    result = split_chunk_docs(chunks, tokens_per_chunk=2, chunk_overlap=0)

    assert [d["id"] for d in result] == ["c1", "c1_1"]
    assert [d["text"] for d in result] == ["a b", "c d"]
    assert [d["char_offset"] for d in result] == [0, 3]
    assert [d["char_length"] for d in result] == [3, 3]


def test_write_chunk_docs_creates_json_file(tmp_path):
    import json

    from features.f5.chunk_utils import CHUNK_FILENAME, write_chunk_docs

    chunks = [{"id": "x"}]
    path = write_chunk_docs(tmp_path, chunks)
    assert path.exists()
    assert path.name == CHUNK_FILENAME
    with open(path) as fh:
        assert json.load(fh) == chunks


def test_content_to_chunk_docs_accepts_string_and_list():
    from features.f5.chunk_utils import content_to_chunk_docs

    docs1 = content_to_chunk_docs(
        "a b c d",
        "f",
        "m",
        file_mtime=10.0,
        tokens_per_chunk=2,
        chunk_overlap=0,
    )
    assert [d["id"] for d in docs1] == ["m_f_0", "m_f_0_1"]
    assert [d["start_time"] for d in docs1] == [10.0, 10.0]

    docs2 = content_to_chunk_docs(
        [
            {"text": "hello", "time_offset": 1},
            {"text": "there", "time_length": 2},
        ],
        "f",
        "m",
        tokens_per_chunk=100,
        file_mtime=10.0,
    )
    assert docs2[0]["time_offset"] == 1
    assert docs2[1]["time_length"] == 2
    assert [d["char_offset"] for d in docs2] == [0, 5]
    assert [d["char_length"] for d in docs2] == [5, 5]
    assert [d["start_time"] for d in docs2] == [11.0, 10.0]


def _reload_chunk_utils(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    monkeypatch.setenv("CHUNK_SETTINGS_FILE_PATH", str(tmp_path / "settings.json"))
    return importlib.reload(__import__("features.f5.chunk_utils", fromlist=["*"]))


def test_chunk_settings_round_trip(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    cu = _reload_chunk_utils(monkeypatch, tmp_path)
    cu.save_chunk_settings()
    assert cu.get_is_chunk_settings_changed() is False
    monkeypatch.setenv("TOKENS_PER_CHUNK", "999")
    cu2 = _reload_chunk_utils(monkeypatch, tmp_path)
    assert cu2.get_is_chunk_settings_changed() is True
