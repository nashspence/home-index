import os
from typing import List, Optional, TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover
    from sentence_transformers import SentenceTransformer

EMBED_MODEL_NAME = os.environ.get("EMBED_MODEL_NAME", "intfloat/e5-small-v2")
try:
    import torch

    _default_device = "cuda" if torch.cuda.is_available() else "cpu"
except Exception:
    _default_device = "cpu"
EMBED_DEVICE = os.environ.get("EMBED_DEVICE", _default_device)
EMBED_DIM = int(os.environ.get("EMBED_DIM", "384"))

_embedding_model: Optional["SentenceTransformer"] = None
# expose for external patching in tests
embedding_model = _embedding_model


def init_embedder() -> None:
    """Initialize the sentence transformer model on first use."""
    global _embedding_model, embedding_model
    if _embedding_model is None:
        from sentence_transformers import SentenceTransformer

        _embedding_model = SentenceTransformer(EMBED_MODEL_NAME, device=EMBED_DEVICE)
        embedding_model = _embedding_model


def embed_texts(texts: List[str]) -> List[List[float]]:
    """Return embeddings for a list of texts."""
    global embedding_model
    if embedding_model is None:
        init_embedder()
        assert embedding_model is not None
    vectors = embedding_model.encode(texts, convert_to_numpy=True)
    return [vec.tolist() for vec in vectors]
