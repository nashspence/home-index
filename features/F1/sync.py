from __future__ import annotations

import asyncio
import copy
import json
import os
import shutil
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor, as_completed
from multiprocessing import Process
from pathlib import Path
from typing import Any, Mapping, MutableMapping, Callable, Awaitable, Coroutine, cast

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
import mimetypes

from features.F1 import scheduler
from features.F2 import duplicate_finder, metadata_store, migrations, path_links
from features.F2 import search_index
from features.F3 import archive
from features.F4 import modules as modules_f4
from features.F5 import chunking
from shared.logging_config import files_logger

INDEX_DIRECTORY = Path(os.environ.get("INDEX_DIRECTORY", "/files"))

CPU_COUNT = os.cpu_count() or 1
MAX_HASH_WORKERS = int(os.environ.get("MAX_HASH_WORKERS", CPU_COUNT // 2))
MAX_FILE_WORKERS = int(os.environ.get("MAX_FILE_WORKERS", CPU_COUNT // 2))

RESERVED_FILES_DIRS = [metadata_store.metadata_directory()]


def _safe_mkdir(path: Path) -> None:
    try:
        path.mkdir(parents=True, exist_ok=True)
    except PermissionError:
        pass
    except OSError as e:
        if e.errno != 30:
            raise


def compute_hash(path: Path) -> tuple[Path, str, os.stat_result]:
    stat = path.stat()
    return path, duplicate_finder.compute_hash(path), stat


_safe_mkdir(INDEX_DIRECTORY)
_safe_mkdir(archive.archive_directory())
metadata_store.ensure_directories()
path_links.ensure_directories()


def module_metadata_path(file_id: str, module_name: str) -> Path:
    path = metadata_store.by_id_directory() / file_id / module_name
    path.mkdir(parents=True, exist_ok=True)
    return path


# Cron helpers
parse_cron_env = scheduler.parse_cron_env

# Validate cron expression on import so startup fails fast.
if str(os.environ.get("DEBUG", "False")) != "True":
    try:
        CronTrigger(**parse_cron_env())
    except ValueError:
        files_logger.error("invalid cron expression")
        raise


# --- sync helpers -----------------------------------------------------------


def write_doc_json(doc: MutableMapping[str, Any]) -> None:
    metadata_store.write_doc_json(doc)


def is_apple_double(file_path: Path) -> bool:
    try:
        with file_path.open("rb") as file:
            return file.read(4) == b"\x00\x05\x16\x07"
    except Exception:
        return False


magic_mime = None


def get_mime_type(file_path: Path) -> str:
    global magic_mime
    if magic_mime is None:
        import magic

        magic_mime = magic.Magic(mime=True)
    mime_type = cast(str, magic_mime.from_file(str(file_path)))
    if mime_type == "application/octet-stream":
        if is_apple_double(file_path):
            return "multipart/appledouble"
        guess, _ = mimetypes.guess_type(str(file_path), strict=False)
        mime_type = guess or "application/octet-stream"
    return mime_type


# --- indexing ---------------------------------------------------------------


def index_metadata() -> tuple[
    dict[str, dict[str, Any]],
    dict[str, str],
    dict[str, dict[str, Any]],
    dict[str, str],
    dict[str, dict[str, Any]],
]:
    metadata_docs_by_hash = {}
    metadata_hashes_by_relpath = {}
    unmounted_archive_docs_by_hash = {}
    unmounted_archive_hashes_by_relpath = {}
    migrated_docs_by_hash = {}

    files_logger.info(" * iterate metadata by-id")
    file_paths = [
        dir / "document.json" for dir in (metadata_store.by_id_directory()).iterdir()
    ]

    def read_doc_json(doc_json_path: Path) -> dict[str, Any] | None:
        if not doc_json_path.exists():
            shutil.rmtree(doc_json_path.parent)
            return None
        with doc_json_path.open("r") as file:
            return cast(dict[str, Any], json.load(file))

    def handle_doc(doc: dict[str, Any] | None) -> None:
        if not doc:
            return
        if migrations.migrate_doc(doc):
            metadata_store.write_doc_json(doc)
            migrated_docs_by_hash[doc["id"]] = doc
        hash_val = doc["id"]
        if hash_val in metadata_docs_by_hash:
            return
        for k in list(doc.keys()):
            if k.endswith(".content"):
                doc.pop(k)
        original_has_archive = doc.get("has_archive_paths")
        original_offline = doc.get("offline")
        archive.update_archive_flags(doc)
        if (
            doc.get("has_archive_paths") != original_has_archive
            or doc.get("offline") != original_offline
        ):
            metadata_store.write_doc_json(doc)
            migrated_docs_by_hash[hash_val] = doc
        metadata_docs_by_hash[hash_val] = doc

        if all(
            archive.is_in_archive_dir(archive.path_from_relpath(relpath))
            and not archive.path_from_relpath(relpath).exists()
            for relpath in doc["paths"].keys()
        ):
            doc_copy = copy.deepcopy(doc)
            archive.update_archive_flags(doc_copy)
            unmounted_archive_docs_by_hash[hash_val] = doc_copy

        unmounted_archive_hashes_by_relpath.update(
            {
                relpath: hash_val
                for relpath in doc["paths"].keys()
                if archive.is_in_archive_dir(archive.path_from_relpath(relpath))
                and not archive.path_from_relpath(relpath).exists()
            }
        )

        metadata_hashes_by_relpath.update(
            {relpath: hash_val for relpath in doc["paths"].keys()}
        )

    if file_paths:
        files_logger.info(" * check %d file hashes", len(file_paths))
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
    metadata_docs_by_hash: dict[str, dict[str, Any]],
    metadata_hashes_by_relpath: dict[str, str],
    unmounted_archive_docs_by_hash: dict[str, dict[str, Any]],
    unmounted_archive_hashes_by_relpath: dict[str, str],
) -> tuple[dict[str, dict[str, Any]], dict[str, str]]:
    files_docs_by_hash: dict[str, dict[str, Any]] = {}
    files_hashes_by_relpath: dict[str, str] = {}

    files_logger.info(" * recursively walk files")
    file_paths = []
    for root, _, files in os.walk(INDEX_DIRECTORY):
        root_path = Path(root)
        if any(
            root_path == dir or dir in root_path.parents for dir in RESERVED_FILES_DIRS
        ):
            continue
        for f in files:
            path = root_path / f
            if archive.is_status_marker(path):
                continue
            file_paths.append(path)

    def handle_hash_at_path(args: tuple[Path, str, os.stat_result]) -> None:
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
                if archive.is_in_archive_dir(archive.path_from_relpath(relpath))
                and not archive.path_from_relpath(relpath).exists()
            }
            doc = metadata_doc
        elif files_doc:
            doc = files_doc
        else:
            doc = {
                "id": hash_val,
                "paths": {relpath: stat.st_mtime},
                "mtime": stat.st_mtime,
                "size": stat.st_size,
                "type": get_mime_type(path),
                "next": "",
            }
        doc.setdefault("paths_list", sorted(doc["paths"].keys()))
        doc.setdefault("copies", len(doc["paths"]))
        doc.setdefault("version", migrations.CURRENT_VERSION)
        archive.update_archive_flags(doc)
        files_docs_by_hash[doc["id"]] = doc
        files_hashes_by_relpath[relpath] = doc["id"]

    if file_paths:
        files_logger.info(" * hash %d files", len(file_paths))
        if MAX_HASH_WORKERS < 2:
            for fp in file_paths:
                handle_hash_at_path(compute_hash(fp))
        else:
            with ProcessPoolExecutor(max_workers=MAX_HASH_WORKERS) as executor:
                for completed in as_completed(
                    executor.submit(compute_hash, fp) for fp in file_paths
                ):
                    handle_hash_at_path(completed.result())

    for doc in metadata_docs_by_hash.values():
        paths = list(doc.get("paths", {}).keys())
        if not paths:
            continue
        sample = archive.path_from_relpath(paths[0])
        drive = archive.drive_name_from_path(sample)
        if drive and not (archive.archive_directory() / drive).exists():
            files_docs_by_hash[doc["id"]] = copy.deepcopy(doc)
            for relpath in paths:
                files_hashes_by_relpath[relpath] = doc["id"]

    if files_docs_by_hash:
        files_logger.info(" * set next modules")
        modules_f4.set_next_modules(
            files_docs_by_hash, force_offline=modules_f4.is_modules_changed
        )

    return files_docs_by_hash, files_hashes_by_relpath


def update_metadata(
    metadata_docs_by_hash: dict[str, dict[str, Any]],
    metadata_hashes_by_relpath: dict[str, str],
    files_docs_by_hash: dict[str, dict[str, Any]],
    files_hashes_by_relpath: dict[str, str],
) -> tuple[dict[str, dict[str, Any]], dict[str, dict[str, Any]]]:
    files_logger.info(" * check for upserted documents")
    upserted_docs_by_hash = {
        hash_val: files_doc
        for hash_val, files_doc in files_docs_by_hash.items()
        if (
            hash_val not in metadata_docs_by_hash
            or metadata_docs_by_hash[hash_val]["paths"]
            != files_docs_by_hash[hash_val]["paths"]
            or metadata_docs_by_hash[hash_val].get("next")
            != files_docs_by_hash[hash_val].get("next")
            or metadata_docs_by_hash[hash_val].get("paths_list")
            != files_docs_by_hash[hash_val].get("paths_list")
            or metadata_docs_by_hash[hash_val].get("version", 0)
            != migrations.CURRENT_VERSION
            or metadata_docs_by_hash[hash_val].get("has_archive_paths")
            != files_docs_by_hash[hash_val].get("has_archive_paths")
            or metadata_docs_by_hash[hash_val].get("offline")
            != files_docs_by_hash[hash_val].get("offline")
        )
    }

    files_logger.info(" * check for deleted file path")
    deleted_relpaths = set(metadata_hashes_by_relpath.keys()) - set(
        files_hashes_by_relpath.keys()
    )

    def handle_deleted_relpath(relpath: str) -> None:
        metadata_doc = metadata_docs_by_hash[metadata_hashes_by_relpath[relpath]]
        by_id_path = metadata_store.by_id_directory() / metadata_doc["id"]
        if metadata_doc["id"] not in files_docs_by_hash and by_id_path.exists():
            shutil.rmtree(by_id_path)
        path_links.unlink_path(relpath)

    def handle_upserted_doc(doc: dict[str, Any]) -> None:
        write_doc_json(doc)
        for relpath in doc["paths"].keys():
            path_links.link_path(relpath, doc["id"])

    if deleted_relpaths:
        files_logger.info(" * delete %d metadata paths", len(deleted_relpaths))
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
        files_logger.info(" * upsert %d metadata documents", len(upserted_docs_by_hash))
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


async def update_meilisearch(
    upserted_docs_by_hash: dict[str, dict[str, Any]],
    files_docs_by_hash: Mapping[str, Mapping[str, Any]],
) -> None:
    files_logger.info(" * get all meilisearch documents")
    all_meili_docs = await search_index.get_all_documents()
    meili_hashes = {doc["id"] for doc in all_meili_docs}

    files_logger.info(" * check for redundant meilisearch documents")
    deleted_hashes = meili_hashes - set(files_docs_by_hash.keys())

    files_logger.info(" * check for missing meilisearch documents")
    missing_meili_hashes = set(files_docs_by_hash.keys()) - meili_hashes
    upserted_docs_by_hash.update(
        {
            hash_val: cast(dict[str, Any], files_docs_by_hash[hash_val])
            for hash_val in missing_meili_hashes
        }
    )

    if deleted_hashes:
        files_logger.info(" * delete %d meilisearch documents", len(deleted_hashes))
        await search_index.delete_docs_by_id(list(deleted_hashes))
        await search_index.delete_chunk_docs_by_file_ids(list(deleted_hashes))
        await search_index.wait_for_meili_idle()
    if upserted_docs_by_hash:
        files_logger.info(
            " * upsert %d meilisearch documents", len(upserted_docs_by_hash)
        )
        await search_index.add_or_update_documents(list(upserted_docs_by_hash.values()))
        await search_index.wait_for_meili_idle()
    total_docs_in_meili = await search_index.get_document_count()
    files_logger.info(" * counted %d documents in meilisearch", total_docs_in_meili)

    # Ensure module queues are refreshed immediately after sync
    if modules_f4.module_values and upserted_docs_by_hash:
        await asyncio.gather(
            *[
                modules_f4.service_module_queue(
                    mod["name"], docs=upserted_docs_by_hash.values()
                )
                for mod in modules_f4.module_values
            ]
        )


async def sync_documents() -> None:
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

        archive.update_drive_markers(files_docs_by_hash)

        upserted_docs_by_hash.update(migrated_docs_by_hash)

        files_logger.info("commit changes to meilisearch")
        await update_meilisearch(upserted_docs_by_hash, files_docs_by_hash)
        await chunking.sync_content_files(files_docs_by_hash)
        files_logger.info("completed file sync")
    except Exception:  # pragma: no cover - unexpected errors
        files_logger.exception("sync failed")
        raise


# --- scheduler orchestration -----------------------------------------------


def run_async_in_loop(
    func: Callable[..., Coroutine[Any, Any, Any]], *args: Any
) -> None:
    asyncio.run(func(*args))


def run_in_process(func: Callable[..., Coroutine[Any, Any, Any]], *args: Any) -> None:
    process = Process(target=run_async_in_loop, args=(func,) + args)
    process.start()
    process.join()


async def init_meili_and_sync() -> None:
    await search_index.init_meili()
    await sync_documents()


async def schedule_and_run(
    api_coro_fn: Callable[[], Awaitable[Any]], *, debug: bool
) -> None:
    """Run the API server and schedule periodic sync jobs."""
    sched = BackgroundScheduler()
    scheduler.attach_sync_job(
        sched,
        debug,
        lambda: run_in_process(init_meili_and_sync),
    )
    sched.start()
    await api_coro_fn()
