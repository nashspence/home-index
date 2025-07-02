from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterable, Mapping

from shared.chunk import CHUNK_MODEL_NAME, TOKENS_PER_CHUNK, CHUNK_OVERLAP


__all__ = [
    "segments_to_chunk_docs",
    "write_chunk_docs",
]


CHUNK_TOKENS_PER_CHUNK = TOKENS_PER_CHUNK


def segments_to_chunk_docs(
    segments: Iterable[Mapping[str, Any]],
    file_id: str,
    module_name: str = "chunk",
) -> list[dict[str, Any]]:
    """Convert raw segments to chunk documents with consistent IDs and split them."""

    docs = []

    for idx, segment in enumerate(segments):
        seg_doc = segment.get("doc", {})
        text = seg_doc.get("text")
        if not text:
            continue

        header = segment.get("header") or {}
        header_parts = [f"{k}: {v}" for k, v in header.items()]
        if header_parts:
            text = "[" + "|".join(header_parts) + "]\n" + text

        doc = seg_doc.copy()
        doc.setdefault("id", f"{module_name}_{file_id}_{idx}")
        doc.setdefault("file_id", file_id)
        doc.setdefault("module", module_name)
        doc["index"] = idx
        doc["text"] = text

        docs.append(doc)

    try:  # pragma: no cover - optional dependency
        from langchain_core.documents import Document
        from langchain_text_splitters import TokenTextSplitter
        from transformers import AutoTokenizer
    except Exception:  # pragma: no cover - optional dependency
        return docs

    lc_docs = []
    for d in docs:
        meta = d.copy()
        text = meta.pop("text")
        lc_docs.append(Document(page_content=text, metadata=meta))

    hf_tok = AutoTokenizer.from_pretrained(CHUNK_MODEL_NAME)
    splitter = TokenTextSplitter.from_huggingface_tokenizer(
        hf_tok,
        chunk_size=CHUNK_TOKENS_PER_CHUNK,
        chunk_overlap=CHUNK_OVERLAP,
    )

    split_docs = splitter.split_documents(lc_docs)

    counts: dict[str, int] = {}
    result = []
    for doc in split_docs:
        base_id = doc.metadata.get("id")
        n = counts.get(base_id, 0)
        counts[base_id] = n + 1

        meta = doc.metadata.copy()
        meta["id"] = f"{base_id}_{n}" if n else base_id
        meta["text"] = doc.page_content.lstrip()

        result.append(meta)

    return result


def write_chunk_docs(
    metadata_dir_path: Path,
    chunk_docs: Iterable[Mapping[str, Any]],
    filename: str = "chunks.json",
) -> Path:
    """Write ``chunk_docs`` to ``filename`` and return the path."""
    path = Path(metadata_dir_path) / filename
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w") as fh:
        json.dump(list(chunk_docs), fh, indent=4)
    return path
