def test_segments_with_headers_convert_to_chunk_documents_referencing_the_source_file():
    from features.F4.home_index_module import segments_to_chunk_docs

    segments = [
        {"header": {"speaker": "A"}, "doc": {"text": "hello"}},
        {"doc": {"text": "bye"}},
    ]

    docs = segments_to_chunk_docs(segments, "file1", module_name="mod")
    assert [d["id"] for d in docs] == ["mod_file1_0", "mod_file1_1"]
    assert docs[0]["file_id"] == "file1"
    assert docs[0]["index"] == 0
    assert docs[0]["text"].startswith("[speaker: A]")


def test_tokentextsplitter_divides_chunk_text_into_smaller_documents(monkeypatch):
    import importlib
    from features.F5 import chunk_utils
    import features.F4.home_index_module as hi_module
    import shared.chunk as chunk_conf

    monkeypatch.setenv("TOKENS_PER_CHUNK", "2")
    monkeypatch.setenv("CHUNK_OVERLAP", "0")
    importlib.reload(chunk_conf)
    importlib.reload(chunk_utils)
    importlib.reload(hi_module)
    segments_to_chunk_docs = hi_module.segments_to_chunk_docs

    segments = [{"doc": {"text": "a b c d"}}]
    result = segments_to_chunk_docs(segments, "f", module_name="m")

    assert [d["id"] for d in result] == ["m_f_0", "m_f_0_1"]
    assert [d["text"] for d in result] == ["a b", "c d"]


def test_write_chunk_docs_creates_json_file(tmp_path):
    import json

    from features.F4.home_index_module import write_chunk_docs

    chunks = [{"id": "x"}]
    path = write_chunk_docs(tmp_path, chunks)
    assert path.exists()
    with open(path) as fh:
        assert json.load(fh) == chunks
