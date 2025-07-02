import os

CHUNK_MODEL_NAME = os.environ.get("CHUNK_MODEL_NAME", "intfloat/e5-small-v2")
TOKENS_PER_CHUNK = int(os.environ.get("TOKENS_PER_CHUNK", "510"))
CHUNK_OVERLAP = int(os.environ.get("CHUNK_OVERLAP", "50"))

__all__ = [
    "CHUNK_MODEL_NAME",
    "TOKENS_PER_CHUNK",
    "CHUNK_OVERLAP",
]
