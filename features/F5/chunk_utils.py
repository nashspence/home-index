from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Iterable, Mapping


EMBED_MODEL_NAME = os.environ.get("EMBED_MODEL_NAME", "intfloat/e5-small-v2")

__all__ = [
    "segments_to_chunk_docs",
    "split_chunk_docs",
    "content_to_chunk_docs",
    "write_chunk_docs",
    "CHUNK_FILENAME",
    "CONTENT_FILENAME",
]

TOKENS_PER_CHUNK = int(os.environ.get("TOKENS_PER_CHUNK", "510"))
CHUNK_OVERLAP = int(os.environ.get("CHUNK_OVERLAP", "50"))

CHUNK_FILENAME = "chunks.json"
CONTENT_FILENAME = "content.json"


def segments_to_chunk_docs(
    segments: Iterable[Mapping[str, Any]],
    file_id: str,
    module_name: str = "chunk",
) -> list[dict[str, Any]]:
    """Convert raw segments to chunk documents with consistent IDs.

    Each ``segment`` may provide a ``header`` mapping which is formatted as a
    leading line in the chunk text.
    """

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

    return docs


def split_chunk_docs(
    chunk_docs: Iterable[dict[str, Any]],
    model: str = "intfloat/e5-small-v2",
    tokens_per_chunk: int = TOKENS_PER_CHUNK,
    chunk_overlap: int = CHUNK_OVERLAP,
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
    char_offset_total = 0
    result = []
    for doc in split_docs:
        base_id = doc.metadata.get("id")
        n = counts.get(base_id, 0)
        counts[base_id] = n + 1

        meta = doc.metadata.copy()
        meta["id"] = f"{base_id}_{n}" if n else base_id
        text = doc.page_content.lstrip()
        meta["text"] = text
        meta.setdefault("char_offset", char_offset_total)
        meta.setdefault("char_length", len(text))
        char_offset_total += len(text)

        result.append(meta)

    return result


def content_to_chunk_docs(
    content: str | Iterable[Mapping[str, Any]],
    file_id: str,
    module_name: str = "chunk",
    *,
    file_mtime: float | None = None,
    model: str = "intfloat/e5-small-v2",
    tokens_per_chunk: int = TOKENS_PER_CHUNK,
    chunk_overlap: int = CHUNK_OVERLAP,
) -> list[dict[str, Any]]:
    """Convert ``content`` into chunk documents for ``file_id``.

    ``content`` may be a single string or an iterable of mappings each
    containing ``text`` and optional metadata such as ``offset`` and ``length``.
    ``segments_to_chunk_docs`` handles the header formatting while
    ``split_chunk_docs`` ensures oversized passages are divided by token count.
    """

    if isinstance(content, str):
        segments = [{"doc": {"text": content}}]
    else:
        segments = []
        for item in content:
            if isinstance(item, str):
                segments.append({"doc": {"text": item}})
            else:
                segments.append({"doc": dict(item)})

    docs = segments_to_chunk_docs(segments, file_id, module_name=module_name)
    docs = split_chunk_docs(
        docs,
        model=model,
        tokens_per_chunk=tokens_per_chunk,
        chunk_overlap=chunk_overlap,
    )

    if file_mtime is not None:
        for doc in docs:
            doc.setdefault("start_time", file_mtime + doc.get("time_offset", 0))

    return docs


def write_chunk_docs(
    metadata_dir_path: Path,
    chunk_docs: Iterable[Mapping[str, Any]],
    filename: str = CHUNK_FILENAME,
) -> Path:
    """Write ``chunk_docs`` to ``filename`` and return the path."""
    path = Path(metadata_dir_path) / filename
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w") as fh:
        json.dump(list(chunk_docs), fh, indent=4)
    return path


# chunk settings persistence
CHUNK_SETTINGS_FILE_PATH = Path(
    os.environ.get("CHUNK_SETTINGS_FILE_PATH", "/home-index/chunk_settings.json")
)


def load_chunk_settings() -> dict[str, Any] | None:
    if not CHUNK_SETTINGS_FILE_PATH.exists():
        return None
    with CHUNK_SETTINGS_FILE_PATH.open("r") as file:
        return json.load(file)


def save_chunk_settings() -> None:
    CHUNK_SETTINGS_FILE_PATH.parent.mkdir(parents=True, exist_ok=True)
    with CHUNK_SETTINGS_FILE_PATH.open("w") as file:
        json.dump(
            {
                "EMBED_MODEL_NAME": EMBED_MODEL_NAME,
                "TOKENS_PER_CHUNK": TOKENS_PER_CHUNK,
                "CHUNK_OVERLAP": CHUNK_OVERLAP,
            },
            file,
        )


def get_is_chunk_settings_changed() -> bool:
    current = {
        "EMBED_MODEL_NAME": EMBED_MODEL_NAME,
        "TOKENS_PER_CHUNK": TOKENS_PER_CHUNK,
        "CHUNK_OVERLAP": CHUNK_OVERLAP,
    }
    saved = load_chunk_settings()
    return saved != current


is_chunk_settings_changed = get_is_chunk_settings_changed()

__all__ += [
    "CHUNK_SETTINGS_FILE_PATH",
    "load_chunk_settings",
    "save_chunk_settings",
    "get_is_chunk_settings_changed",
    "is_chunk_settings_changed",
]
