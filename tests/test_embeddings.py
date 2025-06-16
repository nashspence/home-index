import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "packages"))
import home_index.main as hi


class DummyModel:
    def __init__(self, name, device):
        self.name = name
        self.device = device

    def encode(self, texts, convert_to_numpy=True):
        return [[float(len(t))] * hi.EMBED_DIM for t in texts]


def test_embed_texts_produces_vectors(monkeypatch):
    import sentence_transformers

    monkeypatch.setattr(sentence_transformers, "SentenceTransformer", DummyModel)
    hi.embedding_model = None
    result = hi.embed_texts(["a", "bb"])
    assert len(result) == 2
    assert all(len(vec) == hi.EMBED_DIM for vec in result)
    assert result[1][0] == 2.0
