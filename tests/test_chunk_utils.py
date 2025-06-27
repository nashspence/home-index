def test_segments_with_headers_convert_to_chunk_documents_referencing_the_source_file():
    from features.F4.home_index_module.run_server import segments_to_chunk_docs

    segments = [
        {"header": {"speaker": "A"}, "doc": {"text": "hello"}},
        {"doc": {"text": "bye"}},
    ]

    docs = segments_to_chunk_docs(segments, "file1", module_name="mod")
    assert docs[0]["id"] == "mod_file1_0"
    assert docs[0]["file_id"] == "file1"
    assert docs[0]["text"].startswith("[speaker: A]\n")
    assert docs[1]["id"] == "mod_file1_1"
    assert docs[1]["file_id"] == "file1"


def test_tokentextsplitter_divides_chunk_text_into_smaller_documents():
    from features.F4.home_index_module.run_server import split_chunk_docs

    chunks = [{"id": "c1", "file_id": "f", "module": "m", "text": "a b c d"}]
    result = split_chunk_docs(chunks, tokens_per_chunk=2, chunk_overlap=0)

    assert [d["id"] for d in result] == ["c1", "c1_1"]
    assert [d["text"] for d in result] == ["a b", "c d"]
