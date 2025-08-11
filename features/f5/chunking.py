from __future__ import annotations

import json
from typing import Any, Iterable, Mapping, cast

from features.f2 import metadata_store
from features.f5 import chunk_utils


def build_chunk_docs_from_content(
    content: str | Iterable[Mapping[str, Any]],
    file_id: str,
    module_name: str,
    *,
    file_mtime: float | None = None,
) -> list[dict[str, Any]]:
    """Return chunk documents built from ``content``."""
    return chunk_utils.content_to_chunk_docs(
        content,
        file_id,
        module_name,
        file_mtime=file_mtime,
    )


async def add_content_chunks(
    document: Mapping[str, Any], module_name: str, content: Any | None = None
) -> None:
    """Generate and index chunk documents from ``content``."""
    from features.f2 import search_index

    dir_path = metadata_store.by_id_directory() / document["id"] / module_name
    dir_path.mkdir(parents=True, exist_ok=True)
    content_path = dir_path / chunk_utils.CONTENT_FILENAME
    if content is None:
        if not content_path.exists():
            return
        with content_path.open() as fh:
            content = json.load(fh)
    else:
        with content_path.open("w") as fh:
            json.dump(content, fh)
    chunk_path = dir_path / chunk_utils.CHUNK_FILENAME
    if chunk_path.exists():
        chunk_path.unlink()
    await search_index.delete_chunk_docs_by_file_id_and_module(
        document["id"], module_name
    )
    chunks = build_chunk_docs_from_content(
        content,
        document["id"],
        module_name,
        file_mtime=document.get("mtime"),
    )
    chunk_utils.write_chunk_docs(dir_path, chunks)
    await search_index.add_or_update_chunk_documents(chunks)


async def sync_content_files(docs_by_hash: Mapping[str, Mapping[str, Any]]) -> None:
    """Chunk any stored content files and index the resulting docs."""
    from features.f4 import modules as modules_f4

    for doc in docs_by_hash.values():
        mod_dir = metadata_store.by_id_directory() / doc["id"]
        if not mod_dir.exists():
            continue
        for module_dir in mod_dir.iterdir():
            if not module_dir.is_dir():
                continue
            content_path = module_dir / chunk_utils.CONTENT_FILENAME
            chunk_path = module_dir / chunk_utils.CHUNK_FILENAME
            if content_path.exists() and not chunk_path.exists():
                await add_content_chunks(doc, module_dir.name)
        await modules_f4.update_doc_from_module(cast(dict[str, Any], doc))
