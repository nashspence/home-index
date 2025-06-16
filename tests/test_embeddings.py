import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "packages"))


class DummyModel:
    def __init__(self, name, device):
        self.name = name
        self.device = device

    def encode(self, texts, convert_to_numpy=True):
        return [[float(len(t))] * 384 for t in texts]


def test_embed_texts_produces_vectors(monkeypatch, tmp_path):
    import sentence_transformers
    log_dir = tmp_path / "logs"
    log_dir.mkdir()
    monkeypatch.setenv("LOGGING_DIRECTORY", str(log_dir))
    monkeypatch.setattr(sentence_transformers, "SentenceTransformer", DummyModel)

    import home_index.main as hi
    import importlib
    importlib.reload(hi)

    hi.embedding_model = None
    result = hi.embed_texts(["a", "bb"])
    assert len(result) == 2
    assert all(len(vec) == hi.EMBED_DIM for vec in result)
    assert result[1][0] == 2.0
