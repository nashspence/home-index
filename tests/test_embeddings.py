def test_embed_texts_uses_provided_model(monkeypatch):
    import importlib
    import home_index.main as hi

    importlib.reload(hi)

    class DummyModel:
        class Vec(list):
            def tolist(self):
                return list(self)

        def encode(self, texts, convert_to_numpy=True):
            return [self.Vec([len(t)] * hi.EMBED_DIM) for t in texts]

    hi.embedding_model = DummyModel()

    result = hi.embed_texts(["a", "bb"])

    assert result == [[1] * hi.EMBED_DIM, [2] * hi.EMBED_DIM]
