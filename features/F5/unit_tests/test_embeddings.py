def test_embed_texts_uses_provided_model(monkeypatch):
    import importlib
    import shared.embedding as emb

    importlib.reload(emb)

    class DummyModel:
        class Vec(list):
            def tolist(self):
                return list(self)

        def encode(self, texts, convert_to_numpy=True):
            return [self.Vec([len(t)] * emb.EMBED_DIM) for t in texts]

    emb.embedding_model = DummyModel()

    result = emb.embed_texts(["a", "bb"])

    assert result == [[1] * emb.EMBED_DIM, [2] * emb.EMBED_DIM]
