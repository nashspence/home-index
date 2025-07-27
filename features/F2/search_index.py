from __future__ import annotations

import asyncio
import os
from itertools import chain
from typing import Any, Iterable, Mapping, cast

from meilisearch_python_sdk import AsyncClient

from features.F2 import metadata_store
from features.F5 import chunk_utils
from shared.logging_config import files_logger

MEILISEARCH_BATCH_SIZE = int(os.environ.get("MEILISEARCH_BATCH_SIZE", "10000"))
MEILISEARCH_HOST = os.environ.get("MEILISEARCH_HOST", "http://meilisearch:7700")
MEILISEARCH_INDEX_NAME = os.environ.get("MEILISEARCH_INDEX_NAME", "files")
MEILISEARCH_CHUNK_INDEX_NAME = os.environ.get(
    "MEILISEARCH_CHUNK_INDEX_NAME", "file_chunks"
)

client: AsyncClient | None = None
index: Any | None = None
chunk_index: Any | None = None


async def init_meili() -> None:
    """Initialise the Meilisearch indexes."""
    global client, index, chunk_index
    from features.F4 import modules as modules_f4

    client = AsyncClient(MEILISEARCH_HOST)

    if chunk_utils.is_chunk_settings_changed:
        for path in metadata_store.by_id_directory().rglob(chunk_utils.CHUNK_FILENAME):
            try:
                path.unlink(missing_ok=True)
            except Exception:
                pass
        try:
            await client.get_index(MEILISEARCH_CHUNK_INDEX_NAME)
        except Exception as e:  # pragma: no cover - index may not exist
            if getattr(e, "code", None) != "index_not_found":
                files_logger.exception("check chunk index failed")
                raise
        else:
            try:
                task = await client.index(MEILISEARCH_CHUNK_INDEX_NAME).delete()
                await client.wait_for_task(task.task_uid)
            except Exception:
                files_logger.exception("delete chunk index failed")
                raise
        chunk_utils.save_chunk_settings()

    for attempt in range(30):
        try:
            index = await client.get_index(MEILISEARCH_INDEX_NAME)
            break
        except Exception as e:
            if getattr(e, "code", None) != "index_not_found" and attempt < 29:
                files_logger.warning("meili unavailable, retrying in 1s")
                await asyncio.sleep(1)
                continue
            if getattr(e, "code", None) == "index_not_found":
                try:
                    files_logger.info("meili create index '%s'", MEILISEARCH_INDEX_NAME)
                    index = await client.create_index(
                        MEILISEARCH_INDEX_NAME, primary_key="id"
                    )
                except Exception:
                    files_logger.exception("meili create index failed")
                    raise
            else:
                files_logger.exception("meili init failed")
                raise

    try:
        chunk_index = await client.get_index(MEILISEARCH_CHUNK_INDEX_NAME)
    except Exception as e:  # pragma: no cover - index may not exist
        if getattr(e, "code", None) == "index_not_found":
            files_logger.info("create chunk index '%s'", MEILISEARCH_CHUNK_INDEX_NAME)
            chunk_index = await client.create_index(
                MEILISEARCH_CHUNK_INDEX_NAME, primary_key="id"
            )
        else:
            files_logger.exception("meili chunk init failed")
            raise

    files_logger.info("chunk index uid: %s", chunk_index.uid)
    if chunk_index.uid != MEILISEARCH_CHUNK_INDEX_NAME:
        raise RuntimeError(f"Unexpected chunk index uid {chunk_index.uid}")

    try:
        from meilisearch_python_sdk.models.settings import (
            Embedders,
            HuggingFaceEmbedder,
            MeilisearchSettings,
        )

        files_logger.info("create embedder %s", chunk_utils.EMBED_MODEL_NAME)
        task = await chunk_index.update_embedders(
            Embedders(
                embedders={
                    "e5-small": HuggingFaceEmbedder(
                        model=chunk_utils.EMBED_MODEL_NAME,
                        document_template="passage: {{doc.text}}",
                    )
                }
            )
        )
        await client.wait_for_task(task.task_uid)

        files_logger.info("update chunk index settings")
        settings_body = MeilisearchSettings(
            filterable_attributes=["file_id", "module"],
            sortable_attributes=["index"],
        )
        task = await chunk_index.update_settings(settings_body)
        await client.wait_for_task(task.task_uid)
        chunk_utils.save_chunk_settings()
    except Exception:
        files_logger.exception("meili update chunk index settings failed")
        raise

    filterable = [
        "id",
        "mtime",
        "paths",
        "paths_list",
        "size",
        "next",
        "type",
        "copies",
    ] + list(
        chain(
            *[cfg.get("filterable_attributes", []) for cfg in modules_f4.module_configs]
        )
    )

    try:
        files_logger.debug("meili update index attrs")
        assert index is not None
        await index.update_filterable_attributes(filterable)
        await index.update_sortable_attributes(
            [
                "mtime",
                "paths",
                "size",
                "next",
                "type",
                "copies",
            ]
            + list(
                chain(
                    *[
                        cfg.get("sortable_attributes", [])
                        for cfg in modules_f4.module_configs
                    ]
                )
            )
        )
        await wait_for_meili_idle()
    except Exception:
        files_logger.exception("meili update index attrs failed")
        raise


async def get_document_count() -> int:
    if not index:
        raise RuntimeError("meili index did not init")
    stats = await index.get_stats()
    return cast(int, stats.number_of_documents)


async def add_or_update_documents(docs: Iterable[Mapping[str, Any]]) -> None:
    if not index:
        raise RuntimeError("meili index did not init")
    docs_list = list(docs)
    for i in range(0, len(docs_list), MEILISEARCH_BATCH_SIZE):
        batch = docs_list[i : i + MEILISEARCH_BATCH_SIZE]
        await index.update_documents(batch)


async def add_or_update_chunk_documents(docs: Iterable[Mapping[str, Any]]) -> None:
    if not chunk_index:
        raise RuntimeError("meili chunk index did not init")
    docs_list = list(docs)
    for i in range(0, len(docs_list), MEILISEARCH_BATCH_SIZE):
        batch = docs_list[i : i + MEILISEARCH_BATCH_SIZE]
        await chunk_index.update_documents(batch)


async def delete_docs_by_id(ids: list[str]) -> None:
    if not index:
        raise RuntimeError("meili index did not init")
    for i in range(0, len(ids), MEILISEARCH_BATCH_SIZE):
        batch = ids[i : i + MEILISEARCH_BATCH_SIZE]
        await index.delete_documents(ids=batch)


async def delete_chunk_docs_by_id(ids: list[str]) -> None:
    if not chunk_index:
        raise RuntimeError("meili chunk index did not init")
    if not ids:
        return
    for i in range(0, len(ids), MEILISEARCH_BATCH_SIZE):
        batch = ids[i : i + MEILISEARCH_BATCH_SIZE]
        await chunk_index.delete_documents(ids=batch)


async def delete_chunk_docs_by_file_ids(file_ids: Iterable[str]) -> None:
    if not chunk_index:
        raise RuntimeError("meili chunk index did not init")
    docs = []
    offset = 0
    limit = MEILISEARCH_BATCH_SIZE
    while True:
        result = await chunk_index.get_documents(offset=offset, limit=limit)
        docs.extend(result.results)
        if len(result.results) < limit:
            break
        offset += limit
    ids_to_delete = [d["id"] for d in docs if d.get("file_id") in file_ids]
    await delete_chunk_docs_by_id(ids_to_delete)


async def delete_chunk_docs_by_file_id_and_module(file_id: str, module: str) -> None:
    if not chunk_index:
        raise RuntimeError("meili chunk index did not init")
    docs = []
    offset = 0
    limit = MEILISEARCH_BATCH_SIZE
    while True:
        result = await chunk_index.get_documents(offset=offset, limit=limit)
        docs.extend(result.results)
        if len(result.results) < limit:
            break
        offset += limit
    ids_to_delete = [
        d["id"]
        for d in docs
        if d.get("file_id") == file_id and d.get("module") == module
    ]
    await delete_chunk_docs_by_id(ids_to_delete)


async def get_document(doc_id: str) -> Mapping[str, Any]:
    if not index:
        raise RuntimeError("meili index did not init")
    return cast(Mapping[str, Any], await index.get_document(doc_id))


async def get_all_documents() -> list[dict[str, Any]]:
    if not index:
        raise RuntimeError("meili index did not init")
    docs = []
    offset = 0
    limit = MEILISEARCH_BATCH_SIZE
    while True:
        result = await index.get_documents(offset=offset, limit=limit)
        docs.extend(result.results)
        if len(result.results) < limit:
            break
        offset += limit
    return docs


async def get_all_pending_jobs(name: str) -> list[dict[str, Any]]:
    if not index:
        raise RuntimeError("meili index is not initialized")
    docs = []
    offset = 0
    limit = MEILISEARCH_BATCH_SIZE
    filter_query = f"next = {name}"
    while True:
        response = await index.get_documents(
            filter=filter_query, limit=limit, offset=offset
        )
        docs.extend(response.results)
        if len(response.results) < limit:
            break
        offset += limit
    return docs


async def wait_for_meili_idle() -> None:
    if not client:
        raise RuntimeError("meili index did not init")
    while True:
        tasks = await client.get_tasks()
        active = [t for t in tasks.results if t.status in ["enqueued", "processing"]]
        if not active:
            break
        await asyncio.sleep(1)
