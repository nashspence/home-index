import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "packages"))


def test_segments_with_headers_convert_to_chunk_documents_referencing_the_source_file():
    from home_index_module.run_server import segments_to_chunk_docs

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


def test_tokentextsplitter_divides_chunk_text_into_smaller_documents(monkeypatch):
    import importlib
    rs = importlib.import_module("home_index_module.run_server")

    class DummyDocument:
        def __init__(self, page_content, metadata):
            self.page_content = page_content
            self.metadata = metadata

    class DummySplitter:
        def __init__(self):
            pass

        def split_documents(self, docs):
            result = []
            for doc in docs:
                words = doc.page_content.split()
                for i in range(0, len(words), 2):
                    meta = doc.metadata.copy()
                    meta["id"] = f"{meta['id']}_{i//2}" if i else meta["id"]
                    result.append(DummyDocument(" ".join(words[i:i+2]), meta))
            return result

    class DummyTokenizer:
        @classmethod
        def from_pretrained(cls, name):
            return cls()

    import types
    monkeypatch.setitem(sys.modules, "transformers", types.SimpleNamespace(AutoTokenizer=DummyTokenizer))
    monkeypatch.setitem(sys.modules, "langchain_core.documents", types.SimpleNamespace(Document=DummyDocument))
    monkeypatch.setitem(
        sys.modules,
        "langchain_text_splitters",
        types.SimpleNamespace(TokenTextSplitter=type("T", (), {"from_huggingface_tokenizer": lambda *a, **k: DummySplitter()}))
    )

    chunks = [{"id": "c1", "file_id": "f", "module": "m", "text": "a b c d"}]
    result = rs.split_chunk_docs(chunks, tokens_per_chunk=2, chunk_overlap=0)

    assert [d["id"] for d in result] == ["c1", "c1_1"]
    assert [d["text"] for d in result] == ["a b", "c d"]
