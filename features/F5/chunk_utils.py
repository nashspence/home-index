from __future__ import annotations

from typing import Any, Iterable, Mapping


__all__ = ["segments_to_chunk_docs", "split_chunk_docs"]


def segments_to_chunk_docs(
    segments: Iterable[Mapping[str, Any]],
    file_id: str,
    module_name: str = "chunk",
) -> list[dict[str, Any]]:
    """Convert raw segments to chunk documents with consistent IDs."""

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
        doc["text"] = text

        docs.append(doc)

    return docs


def split_chunk_docs(
    chunk_docs: Iterable[dict[str, Any]],
    model: str = "intfloat/e5-small-v2",
    tokens_per_chunk: int = 450,
    chunk_overlap: int = 50,
) -> list[dict[str, Any]]:
    """Return ``chunk_docs`` split by tokens using ``langchain`` utilities."""
    try:  # pragma: no cover - optional dependency
        from langchain_core.documents import Document
        from langchain_text_splitters import TokenTextSplitter
        from transformers import AutoTokenizer
    except Exception as exc:  # pragma: no cover - optional dependency
        raise RuntimeError("langchain is required for split_chunk_docs") from exc

    docs = []
    for d in chunk_docs:
        d = d.copy()
        text = d.pop("text")
        docs.append(Document(page_content=text, metadata=d))

    hf_tok = AutoTokenizer.from_pretrained(model)
    splitter = TokenTextSplitter.from_huggingface_tokenizer(
        hf_tok,
        chunk_size=tokens_per_chunk,
        chunk_overlap=chunk_overlap,
    )

    split_docs = splitter.split_documents(docs)

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
