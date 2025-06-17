import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "packages"))


def test_text_embeddings_use_sentence_transformer_models(tmp_path, monkeypatch):
    log_dir = tmp_path / "logs"
    log_dir.mkdir()
    monkeypatch.setenv("LOGGING_DIRECTORY", str(log_dir))

    import home_index.main as hi
    import importlib

    importlib.reload(hi)

    hi.embedding_model = None
    result = hi.embed_texts(["a", "bb"])
    assert len(result) == 2
    assert all(len(vec) == hi.EMBED_DIM for vec in result)
