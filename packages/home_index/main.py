# region "debugpy"


import logging.handlers
import os
import debugpy

debugpy.listen(("0.0.0.0", 5678))

if str(os.environ.get("WAIT_FOR_DEBUG_CLIENT", "false")).lower() == "true":
    print("Waiting for debugger to attach...")
    debugpy.wait_for_client()
    print("Debugger attached.")
    debugpy.breakpoint()


# endregion
# region "logging"

import logging

logging.basicConfig(
    level=logging.CRITICAL, format="%(asctime)s [%(levelname)s] %(message)s"
)

modules_logger = logging.getLogger("home-index-modules")
modules_logger.setLevel(logging.INFO)
file_handler = logging.handlers.RotatingFileHandler(
    "/storage/modules.log", maxBytes=5_000_000, backupCount=10
)
file_handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
modules_logger.addHandler(file_handler)

files_logger = logging.getLogger("home-index-files")
files_logger.setLevel(logging.INFO)
file_handler = logging.handlers.RotatingFileHandler(
    "/storage/files.log", maxBytes=5_000_000, backupCount=10
)
file_handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
files_logger.addHandler(file_handler)

# endregion
# region "import"


import asyncio
import json
import shutil
import time
import magic
import mimetypes
import xxhash
from xmlrpc.client import ServerProxy
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from multiprocessing import Process
from itertools import chain
from meilisearch_python_sdk import AsyncClient
from pathlib import Path
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor, as_completed


# endregion
# region "config"


VERSION = 1
ALLOWED_TIME_PER_MODULE = int(os.environ.get("ALLOWED_TIME_PER_MODULE", "300"))
MEILISEARCH_BATCH_SIZE = int(os.environ.get("MEILISEARCH_BATCH_SIZE", "10000"))
MEILISEARCH_HOST = os.environ.get("MEILISEARCH_HOST", "http://localhost:7700")
MEILISEARCH_INDEX_NAME = os.environ.get("MEILISEARCH_INDEX_NAME", "files")
RECHECK_TIME_AFTER_COMPLETE = int(os.environ.get("RECHECK_TIME_AFTER_COMPLETE", "1800"))
MAX_HASH_WORKERS = int(os.environ.get("MAX_HASH_WORKERS", 1))
MAX_FILE_WORKERS = int(os.environ.get("MAX_FILE_WORKERS", 1))

INDEX_DIRECTORY = Path(os.environ.get("INDEX_DIRECTORY", "/files"))
INDEX_DIRECTORY.mkdir(parents=True, exist_ok=True)

ARCHIVE_DIRECTORY = Path(os.environ.get("ARCHIVE_DIRECTORY", "/files/archive"))
ARCHIVE_DIRECTORY.mkdir(parents=True, exist_ok=True)

METADATA_DIRECTORY = Path(os.environ.get("METADATA_DIRECTORY", "/files/metadata"))
METADATA_DIRECTORY.mkdir(parents=True, exist_ok=True)

modules = {}
module_values = []
hellos = []
hello_versions = []
hello_versions_changed = False
hello_versions_file_path = Path("/storage/hello_versions.json")

try:
    MODULES = os.environ.get("MODULES", "")
    if MODULES:
        for module_host in MODULES.split(","):
            proxy = ServerProxy(module_host.strip())
            hello = proxy.hello()
            name = hello["name"]
            version = hello["version"]
            hellos.append(hello)
            hello_versions.append([name, version])
            if name in modules:
                raise ValueError(
                    f"multiple modules found with name {name}, this must be unique"
                )
            modules[name] = {"name": name, "proxy": proxy}
            module_values.append(modules[name])
    hello_versions_json = {}
    if hello_versions_file_path.exists():
        with hello_versions_file_path.open("r") as file:
            hello_versions_json = json.load(file)
    known_hello_versions = hello_versions_json.get("hello_versions", "")
    hello_versions_changed = hello_versions != known_hello_versions
except ValueError:
    raise ValueError(
        "MODULES format should be 'http://domain:port,http://domain:port,...'"
    )


initial_module_id = module_values[0]["name"] if module_values else "idle"


def save_modules_state():
    hello_versions_file_path.parent.mkdir(parents=True, exist_ok=True)
    with hello_versions_file_path.open("w") as file:
        json.dump({"hello_versions": hello_versions}, file)


# endregion
# region "meilisearch"


client = None
index = None


async def init_meili():
    global client, index
    logging.debug(f"meili init")
    client = AsyncClient(MEILISEARCH_HOST)

    try:
        index = await client.get_index(MEILISEARCH_INDEX_NAME)
    except Exception as e:
        if getattr(e, "code", None) == "index_not_found":
            try:
                logging.info(f'meili create index "{MEILISEARCH_INDEX_NAME}"')
                index = await client.create_index(
                    MEILISEARCH_INDEX_NAME, primary_key="id"
                )
            except Exception:
                logging.exception(
                    f'meili create index failed "{MEILISEARCH_INDEX_NAME}"'
                )
                raise
        else:
            logging.exception(f"meili init failed")
            raise

    filterable_attributes = [
        "is_archived",
        "mtime",
        "paths",
        "size",
        "status",
        "type",
    ] + list(chain(*[hello["filterable_attributes"] for hello in hellos]))

    try:
        logging.debug(f"meili update index attrs")
        await index.update_filterable_attributes(filterable_attributes)
        await index.update_sortable_attributes(
            [
                "is_archived",
                "mtime",
                "paths",
                "size",
                "status",
                "type",
            ]
            + list(chain(*[hello["sortable_attributes"] for hello in hellos]))
        )
    except Exception:
        logging.exception(f"meili update index attrs failed")
        raise


async def get_document_count():
    if not index:
        raise Exception("meili index did not init")

    try:
        stats = await index.get_stats()
        return stats.number_of_documents
    except Exception:
        logging.exception(f"meili get stats failed")
        raise


async def add_or_update_document(doc):
    if not index:
        raise Exception("meili index did not init")

    if doc:
        try:
            logging.debug(f'index.update_documents "{doc["paths"][0]}" start')
            await index.update_documents([doc])
            logging.debug(f'index.update_documents "{doc["paths"][0]}" done')
        except Exception:
            logging.exception(
                f'index.update_documents "{doc["paths"][0]}" failed: "{[doc]}"'
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
            logging.exception(f"meili update documents failed")
            raise


async def delete_documents_by_id(ids):
    if not index:
        raise Exception("meili index did not init")

    try:
        if ids:
            for i in range(0, len(ids), MEILISEARCH_BATCH_SIZE):
                batch = ids[i : i + MEILISEARCH_BATCH_SIZE]
                await index.delete_documents(ids=batch)
    except Exception:
        logging.exception(f"meili delete documents failed")
        raise


async def get_document(doc_id):
    if not index:
        raise Exception("meili index did not init")

    try:
        doc = await index.get_document(doc_id)
        return doc
    except Exception:
        logging.exception(f"meili get document failed")
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
        logging.exception(f"meili get documents failed")
        raise


async def get_all_pending_jobs(module):
    if not index:
        raise Exception("MeiliSearch index is not initialized.")

    docs = []
    offset = 0
    limit = MEILISEARCH_BATCH_SIZE
    filter_query = f"status = {module.NAME}"

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
        logging.error(f"Failed to get pending jobs from MeiliSearch: {e}")
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
        logging.exception(f"meili wait for idle failed")
        raise


# endregion
# region "sync"


def write_document_json(document_dict):
    doc_id = document_dict["id"]
    doc_path = METADATA_DIRECTORY / doc_id / "document.json"
    metadata_directory_path = METADATA_DIRECTORY / doc_id
    metadata_directory_path.mkdir(parents=True, exist_ok=True)
    with doc_path.open("w") as file:
        json.dump(document_dict, file, indent=4, separators=(", ", ": "))
    version_path = metadata_directory_path / "version.json"
    version_data = {"version": VERSION}
    with version_path.open("w") as version_file:
        json.dump(version_data, version_file, indent=4, separators=(", ", ": "))


def read_document_json(id):
    doc_path = METADATA_DIRECTORY / id / "document.json"
    if not doc_path.exists():
        return None, False
    with doc_path.open("r") as file:
        document = json.load(file)
    version_path = METADATA_DIRECTORY / id / "version.json"
    with version_path.open("r") as version_file:
        version_data = json.load(version_file)
        saved_version = version_data.get("version")
    version_changed = saved_version != VERSION
    return document, version_changed


def get_mime_type(file_path):
    mime = magic.Magic(mime=True)
    mime_type = mime.from_file(file_path)

    if mime_type == "application/octet-stream":
        mime_type, _ = mimetypes.guess_type(file_path)

        if mime_type is None:
            mime_type = "application/octet-stream"

    return mime_type


def path_from_relative_path(relative_path):
    return INDEX_DIRECTORY / relative_path


def is_in_archive_directory(path):
    return ARCHIVE_DIRECTORY in path.parents


def compute_file_hash(file_path):
    hasher = xxhash.xxh64()
    with file_path.open("rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def should_rehash(file_path, existing_doc, rel_path):
    if not existing_doc:
        return True
    existing_mtime = existing_doc["paths"].get(rel_path, 0)
    current_mtime = file_path.stat().st_mtime
    return abs(existing_mtime - current_mtime) >= 1e-6


def process_file(file_path, metadata_docs_by_id, metadata_docs_by_relpath):
    rel_path = file_path.relative_to(INDEX_DIRECTORY).as_posix()
    stat_info = file_path.stat()
    file_mtime = stat_info.st_mtime

    # Check if we already know a doc that references this rel_path
    existing_doc = None
    if rel_path in metadata_docs_by_relpath:
        existing_doc = metadata_docs_by_relpath[rel_path]

    # Only compute the file hash if needed
    if existing_doc and not should_rehash(file_path, existing_doc, rel_path):
        # Reuse old doc_id
        doc_id = existing_doc["id"]
    else:
        doc_id = compute_file_hash(file_path)

    doc = metadata_docs_by_id.get(doc_id)
    if not doc:
        # Create new document metadata
        doc = {
            "id": doc_id,
            "paths": {rel_path: file_mtime},
            "mtime": file_mtime,
            "size": stat_info.st_size,
            "type": get_mime_type(file_path),
            "is_archived": is_in_archive_directory(file_path),
            "status": initial_module_id,
            "copies": 1,
        }

        # We return (doc_id, doc) so the main thread can persist + update dicts
        return (doc_id, doc)
    else:
        # Update existing doc if needed
        updated = False
        old_mtime = doc["paths"].get(rel_path)
        if old_mtime is None or abs(old_mtime - file_mtime) >= 1e-6:
            doc["paths"][rel_path] = file_mtime
            updated = True

        # Recount copies
        copies_count = len(doc["paths"])
        if doc.get("copies", 0) != copies_count:
            doc["copies"] = copies_count
            updated = True

        # Update doc["mtime"] if this file is the newest
        if file_mtime > doc.get("mtime", 0):
            doc["mtime"] = file_mtime
            updated = True

        # Recalculate size based on the first path
        p = next(iter(doc["paths"]))
        abs_p = path_from_relative_path(p)
        new_size = abs_p.stat().st_size
        if new_size != doc.get("size", 0):
            doc["size"] = new_size
            updated = True

        # If the new path is archived or if any path is archived => doc is archived
        was_archived = doc.get("is_archived", False)
        is_archived = any(
            is_in_archive_directory(path_from_relative_path(p)) for p in doc["paths"]
        )
        if is_archived != was_archived:
            doc["is_archived"] = is_archived
            updated = True

        # Update doc type if needed
        new_type = get_mime_type(file_path)
        if new_type != doc.get("type"):
            doc["type"] = new_type
            updated = True

        if hello_versions_changed:
            doc["status"] = initial_module_id

        if updated:
            return (doc_id, doc)
        else:
            return None


async def sync_documents():
    try:
        files_logger.info("start")

        def handle_metadata_walk_entry(entry):
            if entry.is_dir():
                no_longer_exists = False
                is_updated = False
                doc, _ = read_document_json(entry.name)
                if doc and isinstance(doc.get("paths", {}), dict):
                    paths_that_still_exist = {}
                    for rel_path in doc["paths"].keys():
                        path = path_from_relative_path(rel_path)
                        exists = path.exists()
                        archive = is_in_archive_directory(path)
                        if (
                            (
                                archive
                                and exists
                                and path.stat().st_mtime == doc["paths"][rel_path]
                            )
                            or (archive and not exists)
                            or (exists and not archive)
                        ):
                            paths_that_still_exist[rel_path] = doc["paths"][rel_path]
                            metadata_docs_by_relpath[rel_path] = doc
                        else:
                            is_updated = True
                            continue
                    if not paths_that_still_exist:
                        no_longer_exists = True
                    else:
                        if is_updated:
                            doc["paths"] = paths_that_still_exist
                            doc["copies"] = len(doc["paths"])
                            doc["mtime"] = max(doc["paths"].values())
                            doc["is_archived"] = any(
                                is_in_archive_directory(path_from_relative_path(p))
                                for p in doc["paths"]
                            )
                return doc, no_longer_exists, is_updated

        # Load metadata documents
        files_logger.info(f'get all metadata from "{METADATA_DIRECTORY}"')
        metadata_docs_by_id = {}
        metadata_docs_by_relpath = {}
        docs_to_delete = {}
        docs_to_add_or_update = {}

        def handle_walk_entry_result(result):
            doc, no_longer_exists, is_updated = result
            if no_longer_exists:
                docs_to_delete[doc["id"]] = doc
            else:
                if is_updated:
                    docs_to_add_or_update[doc["id"]] = doc
                metadata_docs_by_id[doc["id"]] = doc
                metadata_docs_by_relpath.update(
                    {relpath: doc for relpath, _ in doc["paths"].items()}
                )

        if MAX_FILE_WORKERS < 2:
            for entry in METADATA_DIRECTORY.iterdir():
                handle_walk_entry_result(handle_metadata_walk_entry(entry))
        else:
            with ThreadPoolExecutor(max_workers=MAX_FILE_WORKERS) as executor:
                for completed in as_completed(
                    executor.submit(handle_metadata_walk_entry, entry)
                    for entry in METADATA_DIRECTORY.iterdir()
                ):
                    handle_walk_entry_result(completed.result())

        # Fetch MeiliSearch documents
        files_logger.info(f"get all meili documents")
        meili_docs = await get_all_documents()
        meili_docs_by_id = {d["id"]: d for d in meili_docs}

        # Gather files from INDEX_DIRECTORY
        files_logger.info(f'get all existing file paths in "{INDEX_DIRECTORY}"')
        file_paths = []
        for root, _, files in INDEX_DIRECTORY.walk():
            # Skip if root is the METADATA_DIRECTORY or any of its subdirectories
            if METADATA_DIRECTORY in root.parents:
                continue
            for f in files:
                file_paths.append(root / f)

        # Process files in parallel
        files_logger.info(f"check for new and/or updated documents")

        def handle_document_update(result):
            if result is not None:
                doc_id, doc = result
                docs_to_add_or_update[doc_id] = doc

        if MAX_HASH_WORKERS < 2:
            for fp in file_paths:
                handle_document_update(
                    process_file(
                        fp,
                        metadata_docs_by_id,
                        metadata_docs_by_relpath,
                    )
                )
        else:
            with ProcessPoolExecutor(max_workers=MAX_HASH_WORKERS) as executor:
                for completed in as_completed(
                    executor.submit(
                        process_file,
                        fp,
                        metadata_docs_by_id,
                        metadata_docs_by_relpath,
                    )
                    for fp in file_paths
                ):
                    handle_document_update(completed.result())

        # Delete any doc that we've identified as stale
        if docs_to_delete:
            files_logger.info(f"delete {len(docs_to_delete)} out-dated documents")

            if MAX_FILE_WORKERS < 2:
                for id in docs_to_delete.keys():
                    shutil.rmtree(METADATA_DIRECTORY / id)
            else:
                with ThreadPoolExecutor(max_workers=MAX_FILE_WORKERS) as executor:
                    for completed in as_completed(
                        executor.submit(shutil.rmtree, METADATA_DIRECTORY / id)
                        for id in docs_to_delete.keys()
                    ):
                        completed.result()

            out_dated_documents = docs_to_delete.keys() | (
                meili_docs_by_id.keys() - metadata_docs_by_id.keys()
            )

            await delete_documents_by_id(list(out_dated_documents))
            await wait_for_meili_idle()

        # Add or update
        if docs_to_add_or_update:
            files_logger.info(f"add or update {len(docs_to_add_or_update)} documents")

            if MAX_FILE_WORKERS < 2:
                for doc in docs_to_add_or_update.values():
                    write_document_json(doc)
            else:
                with ThreadPoolExecutor(max_workers=MAX_FILE_WORKERS) as executor:
                    for completed in as_completed(
                        executor.submit(write_document_json, doc)
                        for doc in docs_to_add_or_update.values()
                    ):
                        completed.result()

            await add_or_update_documents(list(docs_to_add_or_update.values()))
            await wait_for_meili_idle()

        total_docs_in_meili = await get_document_count()
        save_modules_state()
        files_logger.info(f"{total_docs_in_meili} hashes are now searchable")
        files_logger.info("done")
    except:
        files_logger.exception("sync failed")
        raise


# endregion
# region "run modules"


def file_relpath_from_meili_doc(document):
    return Path(document["paths"][0])


def metadata_dir_relpath_from_doc(name, document):
    return Path(f"{document["id"]}/{name}")


def update_document_status(name, document):
    is_archived = False

    for relative_path in document["paths"]:
        if relative_path.startswith(ARCHIVE_DIRECTORY):
            is_archived = True

    document["is_archived"] = is_archived
    status = "idle"

    file_relpath = file_relpath_from_meili_doc(document)
    metadata_dir_relpath = metadata_dir_relpath_from_doc(name, document)
    for name, proxy in modules:
        if proxy.check(file_relpath, document, metadata_dir_relpath):
            status = name
            break

    document["status"] = status
    write_document_json(document)
    return document


async def run_module(name, proxy):
    try:
        modules_logger.debug(f"{name} select files")
        documents = await get_all_pending_jobs(name)
        documents = sorted(documents, key=lambda x: x["mtime"], reverse=True)
        if documents:
            modules_logger.info(f"{name} started for {len(documents)} documents")
            start_time = time.monotonic()
            for document in documents:
                try:
                    elapsed_time = time.monotonic() - start_time
                    if elapsed_time > ALLOWED_TIME_PER_MODULE:
                        modules_logger.debug(f"{name} exceeded configured allowed time")
                        return True
                    file_relpath = file_relpath_from_meili_doc(document)
                    metadata_dir_relpath = metadata_dir_relpath_from_doc(name, document)
                    document = update_document_status(name, document)
                    if document.get("status", "idle") == name:
                        proxy.run(file_relpath, document, metadata_dir_relpath)
                        document = update_document_status(name, document)
                    modules_logger.info(f'{name} "{file_relpath}" commit update')
                    await add_or_update_document(document)
                except:
                    modules_logger.exception(f'{name} "{document}" failed')
        modules_logger.debug(f"{name} up-to-date")
        return False
    except:
        modules_logger.exception(f"{name} failed")
        return True


async def run_modules():
    modules_logger.info(f"begin modules loop")
    while True:
        run_again = False
        for module in module_values:
            module_did_not_finish = await run_module(module["name"], module["proxy"])
            run_again = run_again or module_did_not_finish
        if not run_again:
            await asyncio.sleep(RECHECK_TIME_AFTER_COMPLETE)


# endregion
# region "set schedule"


def run_async_in_loop(func, *args):
    asyncio.run(func(*args))


def run_in_process(func, *args):
    process = Process(target=run_async_in_loop, args=(func,) + args)
    process.start()
    process.join()


async def main():
    await init_meili()
    scheduler = BackgroundScheduler()
    scheduler.add_job(
        run_in_process,
        IntervalTrigger(seconds=60),  # CronTrigger(hour=3, minute=0),
        args=[sync_documents],
        max_instances=1,
    )
    modules_logger.info(f"perform initial sync on start")
    await sync_documents()
    scheduler.start()
    await run_modules()


if __name__ == "__main__":
    asyncio.run(main())


# endregion
