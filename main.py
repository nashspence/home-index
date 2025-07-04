# ruff: noqa: E402
# region "debugpy"


import os

if str(os.environ.get("DEBUG", "False")) == "True":
    import debugpy

    DEBUGPY_HOST = os.environ.get("DEBUGPY_HOST", "0.0.0.0")
    DEBUGPY_PORT = int(os.environ.get("DEBUGPY_PORT", 5678))
    debugpy.listen((DEBUGPY_HOST, DEBUGPY_PORT))

    if str(os.environ.get("WAIT_FOR_DEBUGPY_CLIENT", "False")) == "True":
        print("Waiting for debugger to attach...")
        debugpy.wait_for_client()
        print("Debugger attached.")
        debugpy.breakpoint()


# endregion
# region "logging"

import logging
import logging.handlers

LOGGING_LEVEL = os.environ.get("LOGGING_LEVEL", "INFO")
LOGGING_MAX_BYTES = int(os.environ.get("LOGGING_MAX_BYTES", 5_000_000))
LOGGING_BACKUP_COUNT = int(os.environ.get("LOGGING_BACKUP_COUNT", 10))

logging.basicConfig(
    level=logging.CRITICAL, format="%(asctime)s [%(levelname)s] %(message)s"
)

LOGGING_DIRECTORY = os.environ.get("LOGGING_DIRECTORY", "/home-index")
os.makedirs(LOGGING_DIRECTORY, exist_ok=True)

files_logger = logging.getLogger("home-index-files")
files_logger.setLevel(LOGGING_LEVEL)
file_handler = logging.handlers.RotatingFileHandler(
    os.path.join(LOGGING_DIRECTORY, "files.log"),
    maxBytes=LOGGING_MAX_BYTES,
    backupCount=LOGGING_BACKUP_COUNT,
)
file_handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
files_logger.addHandler(file_handler)

# endregion
# region "import"


import asyncio
import copy
import json
import mimetypes
import shutil
import sys
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor, as_completed
from itertools import chain
from multiprocessing import Manager, Process
from pathlib import Path
from typing import Any, Iterable, Mapping

import magic
from apscheduler.schedulers.background import BackgroundScheduler
from meilisearch_python_sdk import AsyncClient

# Ensure the 'features' package is importable regardless of install location.
PROJECT_ROOT = Path(__file__).resolve()
while not (PROJECT_ROOT / "features").exists() and PROJECT_ROOT.parent != PROJECT_ROOT:
    PROJECT_ROOT = PROJECT_ROOT.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from features.F1 import scheduler
from features.F2 import duplicate_finder, metadata_store, migrations, path_links
from features.F3 import archive
from features.F4 import modules as modules_f4
from features.F5 import chunk_utils

write_chunk_docs = chunk_utils.write_chunk_docs
is_chunk_settings_changed = chunk_utils.is_chunk_settings_changed
save_chunk_settings = chunk_utils.save_chunk_settings
CHUNK_SETTINGS_FILE_PATH = chunk_utils.CHUNK_SETTINGS_FILE_PATH
CHUNK_FILENAME = chunk_utils.CHUNK_FILENAME

path_from_relpath = archive.path_from_relpath
is_in_archive_dir = archive.is_in_archive_dir
doc_is_online = archive.doc_is_online
update_archive_flags = archive.update_archive_flags

# Expose F2 migration helpers for external use and unit tests.
migrate_doc = migrations.migrate_doc
CURRENT_VERSION = migrations.CURRENT_VERSION


magic_mime = magic.Magic(mime=True)

# expose F4 module helpers
modules_logger = modules_f4.modules_logger
module_values = modules_f4.module_values
modules = modules_f4.modules
module_configs = modules_f4.module_configs
is_modules_changed = modules_f4.is_modules_changed
save_modules_state = modules_f4.save_modules_state
service_module_queue = modules_f4.service_module_queue
service_module_queues = modules_f4.service_module_queues
file_relpath_from_meili_doc = modules_f4.file_relpath_from_meili_doc
metadata_dir_relpath_from_doc = modules_f4.metadata_dir_relpath_from_doc
update_doc_from_module = modules_f4.update_doc_from_module
set_next_modules = modules_f4.set_next_modules

# endregion
# region "config"


DEBUG = str(os.environ.get("DEBUG", "False")) == "True"
COMMIT_SHA = os.environ.get("COMMIT_SHA", "unknown")

MEILISEARCH_BATCH_SIZE = int(os.environ.get("MEILISEARCH_BATCH_SIZE", "10000"))
MEILISEARCH_HOST = os.environ.get("MEILISEARCH_HOST", "http://meilisearch:7700")
MEILISEARCH_INDEX_NAME = os.environ.get("MEILISEARCH_INDEX_NAME", "files")
MEILISEARCH_CHUNK_INDEX_NAME = os.environ.get(
    "MEILISEARCH_CHUNK_INDEX_NAME",
    "file_chunks",
)

CPU_COUNT = os.cpu_count() or 1
MAX_HASH_WORKERS = int(os.environ.get("MAX_HASH_WORKERS", CPU_COUNT // 2))
MAX_FILE_WORKERS = int(os.environ.get("MAX_FILE_WORKERS", CPU_COUNT // 2))

from shared import EMBED_DEVICE, EMBED_DIM, EMBED_MODEL_NAME
from shared.embedding import embed_texts, embedding_model

__all__ = [
    "embed_texts",
    "embedding_model",
    "EMBED_MODEL_NAME",
    "EMBED_DEVICE",
    "EMBED_DIM",
    "module_metadata_path",
    "build_chunk_docs_from_content",
    "add_content_chunks",
    "delete_chunk_docs_by_file_id_and_module",
    "write_chunk_docs",
    "is_chunk_settings_changed",
    "save_chunk_settings",
    "CHUNK_SETTINGS_FILE_PATH",
    "CHUNK_FILENAME",
]

INDEX_DIRECTORY = Path(os.environ.get("INDEX_DIRECTORY", "/files"))


def _safe_mkdir(path: Path) -> None:
    try:
        path.mkdir(parents=True, exist_ok=True)
    except PermissionError:
        # May run in read-only environments during imports
        pass
    except OSError as e:
        if e.errno == 30:  # Read-only file system
            # Ignore read-only file systems so tests can mount /files as ro
            pass
        else:
            raise


_safe_mkdir(INDEX_DIRECTORY)

METADATA_DIRECTORY = metadata_store.metadata_directory()
BY_ID_DIRECTORY = metadata_store.by_id_directory()
metadata_store.ensure_directories()
path_links.ensure_directories()


def module_metadata_path(file_id: str, module_name: str) -> Path:
    """Return the metadata directory path for ``module_name`` and ``file_id``."""
    path = BY_ID_DIRECTORY / file_id / module_name
    path.mkdir(parents=True, exist_ok=True)
    return path


ARCHIVE_DIRECTORY = archive.archive_directory()
_safe_mkdir(ARCHIVE_DIRECTORY)

RESERVED_FILES_DIRS = [METADATA_DIRECTORY]


# embedding helpers
# functions imported from shared


def parse_cron_env(
    env_var: str = "CRON_EXPRESSION", default: str = "0 2 * * *"
) -> dict:
    """Return CronTrigger kwargs for the configured cron expression."""
    return scheduler.parse_cron_env(env_var=env_var, default=default)


# endregion
# region "meilisearch"


client = None
index = None
chunk_index = None


async def init_meili():
    global client, index, chunk_index
    files_logger.debug("meili init")
    client = AsyncClient(MEILISEARCH_HOST)

    if is_chunk_settings_changed:
        for path in BY_ID_DIRECTORY.rglob(CHUNK_FILENAME):
            try:
                path.unlink(missing_ok=True)
            except Exception:
                pass
        try:
            task = await client.index(MEILISEARCH_CHUNK_INDEX_NAME).delete()
            await client.wait_for_task(task.task_uid)
        except Exception as e:
            if getattr(e, "code", None) != "index_not_found":
                files_logger.exception("delete chunk index failed")
                raise
        save_chunk_settings()

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
                    files_logger.info(f'meili create index "{MEILISEARCH_INDEX_NAME}"')
                    index = await client.create_index(
                        MEILISEARCH_INDEX_NAME, primary_key="id"
                    )
                except Exception:
                    files_logger.exception(
                        f'meili create index failed "{MEILISEARCH_INDEX_NAME}"'
                    )
                    raise
            else:
                files_logger.exception("meili init failed")
                raise

    try:
        chunk_index = await client.get_index(MEILISEARCH_CHUNK_INDEX_NAME)
    except Exception as e:
        if getattr(e, "code", None) == "index_not_found":
            try:
                files_logger.info(
                    'meili create index "%s"', MEILISEARCH_CHUNK_INDEX_NAME
                )
                chunk_index = await client.create_index(
                    MEILISEARCH_CHUNK_INDEX_NAME, primary_key="id"
                )
            except Exception:
                files_logger.exception(
                    'meili create index failed "%s"',
                    MEILISEARCH_CHUNK_INDEX_NAME,
                )
                raise
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

        # Register the embedder and wait for the model download
        files_logger.info("create embedder %s", EMBED_MODEL_NAME)
        task = await chunk_index.update_embedders(
            Embedders(
                embedders={
                    "e5-small": HuggingFaceEmbedder(
                        model=EMBED_MODEL_NAME,
                        document_template="passage: {{doc.text}}",
                    )
                }
            )
        )
        await client.wait_for_task(task.task_uid)

        # Configure filterable attributes
        files_logger.info("update chunk index settings")
        settings_body = MeilisearchSettings(
            filterable_attributes=["file_id", "module"],
            sortable_attributes=["index"],
        )
        task = await chunk_index.update_settings(settings_body)
        await client.wait_for_task(task.task_uid)
        save_chunk_settings()
    except Exception:
        files_logger.exception("meili update chunk index settings failed")
        raise

    filterable_attributes = [
        "id",
        "mtime",
        "paths",
        "paths_list",
        "size",
        "next",
        "type",
        "copies",
    ] + list(chain(*[cfg.get("filterable_attributes", []) for cfg in module_configs]))

    try:
        files_logger.debug("meili update index attrs")
        await index.update_filterable_attributes(filterable_attributes)
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
                chain(*[cfg.get("sortable_attributes", []) for cfg in module_configs])
            )
        )
        await wait_for_meili_idle()
    except Exception:
        files_logger.exception("meili update index attrs failed")
        raise


async def get_document_count():
    if not index:
        raise Exception("meili index did not init")

    try:
        stats = await index.get_stats()
        return stats.number_of_documents
    except Exception:
        files_logger.exception("meili get stats failed")
        raise


async def add_or_update_document(doc):
    if not index:
        raise Exception("meili index did not init")

    if doc:
        try:
            files_logger.debug(
                f'index.update_documents "{next(iter(doc["paths"]))}" start'
            )
            await index.update_documents([doc])
            files_logger.debug(
                f'index.update_documents "{next(iter(doc["paths"]))}" done'
            )
        except Exception:
            files_logger.exception(
                f'index.update_documents "{next(iter(doc["paths"]))}" failed: "{[doc]}"'
            )
            raise


async def add_or_update_documents(docs):
    if not index:
        raise Exception("meili index did not init")

    if docs:
        try:
            for i in range(0, len(docs), MEILISEARCH_BATCH_SIZE):
                batch = docs[i : i + MEILISEARCH_BATCH_SIZE]
                await index.update_documents(batch)
        except Exception:
            files_logger.exception("meili update documents failed")
            raise


async def add_or_update_chunk_documents(docs):
    if not chunk_index:
        raise Exception("meili chunk index did not init")

    if docs:
        try:
            for i in range(0, len(docs), MEILISEARCH_BATCH_SIZE):
                batch = docs[i : i + MEILISEARCH_BATCH_SIZE]
                await chunk_index.update_documents(batch)
        except Exception:
            files_logger.exception("meili update chunk documents failed")
            raise


async def delete_docs_by_id(ids):
    if not index:
        raise Exception("meili index did not init")

    try:
        if ids:
            for i in range(0, len(ids), MEILISEARCH_BATCH_SIZE):
                batch = ids[i : i + MEILISEARCH_BATCH_SIZE]
                await index.delete_documents(ids=batch)
    except Exception:
        files_logger.exception("meili delete documents failed")
        raise


async def delete_chunk_docs_by_id(ids):
    if not ids:
        return
    if not chunk_index:
        raise Exception("meili chunk index did not init")

    try:
        if ids:
            for i in range(0, len(ids), MEILISEARCH_BATCH_SIZE):
                batch = ids[i : i + MEILISEARCH_BATCH_SIZE]
                await chunk_index.delete_documents(ids=batch)
    except Exception:
        files_logger.exception("meili delete chunk documents failed")
        raise


async def delete_chunk_docs_by_file_ids(file_ids):
    if not chunk_index:
        raise Exception("meili chunk index did not init")

    try:
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
    except Exception:
        files_logger.exception("meili delete chunk documents by file id failed")
        raise


async def delete_chunk_docs_by_file_id_and_module(file_id: str, module: str) -> None:
    """Delete chunks for ``file_id`` produced by ``module``."""
    if not chunk_index:
        raise Exception("meili chunk index did not init")

    try:
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
    except Exception:
        files_logger.exception(
            "meili delete chunk documents by file id and module failed"
        )
        raise


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


async def add_content_chunks(document: dict[str, Any], module_name: str) -> None:
    """Generate and index chunk documents from ``module_name.content``."""

    key = f"{module_name}.content"
    if key not in document:
        return

    content = document.pop(key)
    dir_path = module_metadata_path(document["id"], module_name)
    file_path = dir_path / CHUNK_FILENAME
    if file_path.exists():
        file_path.unlink()
    await delete_chunk_docs_by_file_id_and_module(document["id"], module_name)
    chunks = build_chunk_docs_from_content(
        content,
        document["id"],
        module_name,
        file_mtime=document.get("mtime"),
    )
    chunk_utils.write_chunk_docs(dir_path, chunks)
    await add_or_update_chunk_documents(chunks)


async def sync_content_fields(docs_by_hash: Mapping[str, dict[str, Any]]) -> None:
    """Chunk any ``<module>.content`` fields and index the resulting docs."""

    for doc in docs_by_hash.values():
        keys = [k for k in doc.keys() if k.endswith(".content")]
        for key in keys:
            module_name = key.split(".")[0]
            dir_path = module_metadata_path(doc["id"], module_name)
            file_path = dir_path / CHUNK_FILENAME
            if not file_path.exists():
                await add_content_chunks(doc, module_name)
            else:
                doc.pop(key)
            await update_doc_from_module(doc)


async def get_document(doc_id):
    if not index:
        raise Exception("meili index did not init")

    try:
        doc = await index.get_document(doc_id)
        return doc
    except Exception:
        files_logger.exception("meili get document failed")
        raise


async def get_all_documents():
    if not index:
        raise Exception("meili index did not init")

    docs = []
    offset = 0
    limit = MEILISEARCH_BATCH_SIZE
    try:
        while True:
            result = await index.get_documents(offset=offset, limit=limit)
            docs.extend(result.results)
            if len(result.results) < limit:
                break
            offset += limit
        return docs
    except Exception:
        files_logger.exception("meili get documents failed")
        raise


async def get_all_pending_jobs(name):
    if not index:
        raise Exception("MeiliSearch index is not initialized.")

    docs = []
    offset = 0
    limit = MEILISEARCH_BATCH_SIZE
    filter_query = f"next = {name}"

    try:
        while True:
            response = await index.get_documents(
                filter=filter_query,
                limit=limit,
                offset=offset,
            )
            docs.extend(response.results)
            if len(response.results) < limit:
                break
            offset += limit
        return docs
    except Exception as e:
        files_logger.error(f"failed to get pending jobs from meilisearch: {e}")
        raise


async def wait_for_meili_idle():
    if not client:
        raise Exception("meili index did not init")

    try:
        while True:
            tasks = await client.get_tasks()
            active_tasks = [
                task
                for task in tasks.results
                if task.status in ["enqueued", "processing"]
            ]
            if len(active_tasks) == 0:
                break
            await asyncio.sleep(1)
    except Exception:
        files_logger.exception("meili wait for idle failed")
        raise


# endregion
# region "sync"


def write_doc_json(doc):
    """Write ``doc`` via Feature F2 utilities."""
    metadata_store.write_doc_json(doc)


def is_apple_double(file_path: Path) -> bool:
    """Return True if ``file_path`` is an AppleDouble header."""
    try:
        with file_path.open("rb") as file:
            return file.read(4) == b"\x00\x05\x16\x07"
    except Exception:
        return False


def get_mime_type(file_path: Path) -> str:
    """Return the MIME type for ``file_path``."""
    mime_type = magic_mime.from_file(str(file_path))
    if mime_type == "application/octet-stream":
        if is_apple_double(file_path):
            return "multipart/appledouble"
        guess, _ = mimetypes.guess_type(str(file_path), strict=False)
        mime_type = guess or "application/octet-stream"
    return mime_type


def index_metadata():
    metadata_docs_by_hash = {}
    metadata_hashes_by_relpath = {}
    unmounted_archive_docs_by_hash = {}
    unmounted_archive_hashes_by_relpath = {}
    migrated_docs_by_hash = {}

    files_logger.info(" * iterate metadata by-id")
    file_paths = [dir / "document.json" for dir in (BY_ID_DIRECTORY).iterdir()]

    def read_doc_json(doc_json_path):
        if not doc_json_path.exists():
            shutil.rmtree(doc_json_path.parent)
            return None
        with doc_json_path.open("r") as file:
            return json.load(file)

    def handle_doc(doc):
        if not doc:
            return
        if migrate_doc(doc):
            metadata_store.write_doc_json(doc)
            migrated_docs_by_hash[doc["id"]] = doc
        hash = doc["id"]
        if hash in metadata_docs_by_hash:
            return

        original_has_archive = doc.get("has_archive_paths")
        original_offline = doc.get("offline")
        update_archive_flags(doc)
        if (
            doc.get("has_archive_paths") != original_has_archive
            or doc.get("offline") != original_offline
        ):
            metadata_store.write_doc_json(doc)
            migrated_docs_by_hash[hash] = doc
        metadata_docs_by_hash[hash] = doc

        if all(
            is_in_archive_dir(path_from_relpath(relpath))
            and not path_from_relpath(relpath).exists()
            for relpath in doc["paths"].keys()
        ):
            doc_copy = copy.deepcopy(doc)
            update_archive_flags(doc_copy)
            unmounted_archive_docs_by_hash[hash] = doc_copy

        unmounted_archive_hashes_by_relpath.update(
            {
                relpath: hash
                for relpath in doc["paths"].keys()
                if is_in_archive_dir(path_from_relpath(relpath))
                and not path_from_relpath(relpath).exists()
            }
        )

        metadata_hashes_by_relpath.update(
            {relpath: hash for relpath in doc["paths"].keys()}
        )

    if file_paths:
        files_logger.info(f" * check {len(file_paths)} file hashes")
        if MAX_FILE_WORKERS < 2:
            for fp in file_paths:
                handle_doc(read_doc_json(fp))
        else:
            with ThreadPoolExecutor(max_workers=MAX_FILE_WORKERS) as executor:
                for completed in as_completed(
                    executor.submit(read_doc_json, fp) for fp in file_paths
                ):
                    handle_doc(completed.result())

    return (
        metadata_docs_by_hash,
        metadata_hashes_by_relpath,
        unmounted_archive_docs_by_hash,
        unmounted_archive_hashes_by_relpath,
        migrated_docs_by_hash,
    )


def index_files(
    metadata_docs_by_hash,
    metadata_hashes_by_relpath,
    unmounted_archive_docs_by_hash,
    unmounted_archive_hashes_by_relpath,
):
    files_docs_by_hash = unmounted_archive_docs_by_hash
    files_hashes_by_relpath = unmounted_archive_hashes_by_relpath

    files_logger.info(" * recursively walk files")
    file_paths = []
    for root, _, files in os.walk(INDEX_DIRECTORY):
        root_path = Path(root)
        if any(
            root_path == dir or dir in root_path.parents for dir in RESERVED_FILES_DIRS
        ):
            continue
        for f in files:
            file_paths.append(root_path / f)

    def handle_hash_at_path(args):
        path, hash_val, stat = args
        relpath = str(path.relative_to(INDEX_DIRECTORY))

        metadata_doc = files_doc = None
        if hash_val in metadata_docs_by_hash:
            metadata_doc = copy.deepcopy(metadata_docs_by_hash[hash_val])
        if hash_val in files_docs_by_hash:
            files_doc = files_docs_by_hash[hash_val]

        if metadata_doc and not files_doc:
            metadata_doc["paths"] = {
                relpath: mtime
                for relpath, mtime in metadata_doc["paths"].items()
                if is_in_archive_dir(path_from_relpath(relpath))
                and not path_from_relpath(relpath).exists()
            }
            doc = metadata_doc
        elif files_doc:
            doc = files_doc
        else:
            doc = {
                "id": hash_val,
                "paths": {},
                "mtime": duplicate_finder.truncate_mtime(stat.st_mtime),
                "size": stat.st_size,
                "type": get_mime_type(path),
            }

        doc["type"] = get_mime_type(path)
        doc["paths"][relpath] = duplicate_finder.truncate_mtime(stat.st_mtime)
        doc["copies"] = len(doc["paths"])
        doc["mtime"] = max(doc["paths"].values())
        doc["paths_list"] = sorted(doc["paths"].keys())
        doc["version"] = CURRENT_VERSION
        update_archive_flags(doc)

        files_docs_by_hash[hash_val] = doc
        files_hashes_by_relpath[relpath] = hash_val

    if file_paths:
        files_logger.info(f" * check {len(file_paths)} file hashes")
        if MAX_HASH_WORKERS < 2:
            for fp in file_paths:
                handle_hash_at_path(
                    duplicate_finder.determine_hash(
                        fp,
                        INDEX_DIRECTORY,
                        metadata_docs_by_hash,
                        metadata_hashes_by_relpath,
                    )
                )
        else:
            manager = Manager()
            shared_docs = manager.dict(metadata_docs_by_hash)
            shared_paths = manager.dict(metadata_hashes_by_relpath)

            with ProcessPoolExecutor(max_workers=MAX_HASH_WORKERS) as executor:
                for completed in as_completed(
                    executor.submit(
                        duplicate_finder.determine_hash,
                        fp,
                        INDEX_DIRECTORY,
                        shared_docs,
                        shared_paths,
                    )
                    for fp in file_paths
                ):
                    handle_hash_at_path(completed.result())

    if files_docs_by_hash:
        files_logger.info(" * set next modules")
        set_next_modules(files_docs_by_hash)

    return files_docs_by_hash, files_hashes_by_relpath


def update_metadata(
    metadata_docs_by_hash,
    metadata_hashes_by_relpath,
    files_docs_by_hash,
    files_hashes_by_relpath,
):
    files_logger.info(" * check for upserted documents")
    upserted_docs_by_hash = {
        hash: files_doc
        for hash, files_doc in files_docs_by_hash.items()
        if (hash not in metadata_docs_by_hash)
        or (metadata_docs_by_hash[hash]["paths"] != files_docs_by_hash[hash]["paths"])
        or (
            metadata_docs_by_hash[hash].get("next")
            != files_docs_by_hash[hash].get("next")
        )
        or (
            metadata_docs_by_hash[hash].get("paths_list")
            != files_docs_by_hash[hash].get("paths_list")
        )
        or (metadata_docs_by_hash[hash].get("version", 0) != CURRENT_VERSION)
        or (
            metadata_docs_by_hash[hash].get("has_archive_paths")
            != files_docs_by_hash[hash].get("has_archive_paths")
        )
        or (
            metadata_docs_by_hash[hash].get("offline")
            != files_docs_by_hash[hash].get("offline")
        )
    }

    files_logger.info(" * check for deleted file path")
    deleted_relpaths = set(metadata_hashes_by_relpath.keys()) - set(
        files_hashes_by_relpath.keys()
    )

    def handle_deleted_relpath(relpath):
        metadata_doc = metadata_docs_by_hash[metadata_hashes_by_relpath[relpath]]
        by_id_path = BY_ID_DIRECTORY / metadata_doc["id"]
        if metadata_doc["id"] not in files_docs_by_hash and by_id_path.exists():
            shutil.rmtree(by_id_path)
        path_links.unlink_path(relpath)

    def handle_upserted_doc(doc):
        write_doc_json(doc)
        for relpath in doc["paths"].keys():
            path_links.link_path(relpath, doc["id"])

    if deleted_relpaths:
        files_logger.info(f" * delete {len(deleted_relpaths)} metadata paths")
        if MAX_FILE_WORKERS < 2:
            for relpath in deleted_relpaths:
                handle_deleted_relpath(relpath)
        else:
            with ThreadPoolExecutor(max_workers=MAX_FILE_WORKERS) as executor:
                for completed in as_completed(
                    executor.submit(handle_deleted_relpath, relpath)
                    for relpath in deleted_relpaths
                ):
                    completed.result()

    if upserted_docs_by_hash:
        files_logger.info(f" * upsert {len(upserted_docs_by_hash)} metadata documents")
        if MAX_FILE_WORKERS < 2:
            for doc in upserted_docs_by_hash.values():
                handle_upserted_doc(doc)
        else:
            with ThreadPoolExecutor(max_workers=MAX_FILE_WORKERS) as executor:
                for completed in as_completed(
                    executor.submit(handle_upserted_doc, doc)
                    for doc in upserted_docs_by_hash.values()
                ):
                    completed.result()

    return upserted_docs_by_hash, files_docs_by_hash


async def update_meilisearch(upserted_docs_by_hash, files_docs_by_hash):
    files_logger.info(" * get all meilisearch documents")
    all_meili_docs = await get_all_documents()
    meili_hashes = {doc["id"] for doc in all_meili_docs}

    files_logger.info(" * check for redundant meilisearch documents")
    deleted_hashes = meili_hashes - set(files_docs_by_hash.keys())

    files_logger.info(" * check for missing meilisearch documents")
    missing_meili_hashes = set(files_docs_by_hash.keys()) - meili_hashes
    upserted_docs_by_hash.update(
        {hash: files_docs_by_hash[hash] for hash in missing_meili_hashes}
    )

    if deleted_hashes:
        files_logger.info(f" * delete {len(deleted_hashes)} meilisearch documents")
        await delete_docs_by_id(list(deleted_hashes))
        await delete_chunk_docs_by_file_ids(list(deleted_hashes))
        await wait_for_meili_idle()
    if upserted_docs_by_hash:
        files_logger.info(
            f" * upsert {len(upserted_docs_by_hash)} meilisearch documents"
        )
        await add_or_update_documents(list(upserted_docs_by_hash.values()))
        await wait_for_meili_idle()
    total_docs_in_meili = await get_document_count()
    files_logger.info(f" * counted {total_docs_in_meili} documents in meilisearch")


async def sync_documents():
    try:
        files_logger.info("---------------------------------------------------")
        files_logger.info("start file sync")
        files_logger.info("index previously stored metadata")
        (
            metadata_docs_by_hash,
            metadata_hashes_by_relpath,
            unmounted_archive_docs_by_hash,
            unmounted_archive_hashes_by_relpath,
            migrated_docs_by_hash,
        ) = index_metadata()

        files_logger.info("index all files")
        files_docs_by_hash, files_hashes_by_relpath = index_files(
            metadata_docs_by_hash,
            metadata_hashes_by_relpath,
            unmounted_archive_docs_by_hash,
            unmounted_archive_hashes_by_relpath,
        )

        files_logger.info("cross-index to update metadata")
        upserted_docs_by_hash, files_docs_by_hash = update_metadata(
            metadata_docs_by_hash,
            metadata_hashes_by_relpath,
            files_docs_by_hash,
            files_hashes_by_relpath,
        )

        upserted_docs_by_hash.update(migrated_docs_by_hash)

        files_logger.info("commit changes to meilisearch")
        await update_meilisearch(upserted_docs_by_hash, files_docs_by_hash)
        await sync_content_fields(files_docs_by_hash)
    except:
        files_logger.exception("sync failed")
        raise


# endregion
# region "set schedule"


def run_async_in_loop(func, *args):
    asyncio.run(func(*args))


def run_in_process(func, *args):
    process = Process(target=run_async_in_loop, args=(func,) + args)
    process.start()
    process.join()


async def init_meili_and_sync():
    await init_meili()
    await sync_documents()


async def main():
    files_logger.info("running commit %s", COMMIT_SHA)
    await init_meili_and_sync()
    sched = BackgroundScheduler()

    scheduler.attach_sync_job(
        sched,
        DEBUG,
        lambda: run_in_process(init_meili_and_sync),
    )

    if is_modules_changed:
        modules_logger.info("*** perform sync on MODULES changed")
        await init_meili_and_sync()
        save_modules_state()

    sched.start()
    await service_module_queues()


if __name__ == "__main__":
    asyncio.run(main())


# endregion
