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
    "/home-index/modules.log", maxBytes=5_000_000, backupCount=10
)
file_handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
modules_logger.addHandler(file_handler)

files_logger = logging.getLogger("home-index-files")
files_logger.setLevel(logging.INFO)
file_handler = logging.handlers.RotatingFileHandler(
    "/home-index/files.log", maxBytes=5_000_000, backupCount=10
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
import copy
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

INDEX_DIRECTORY = Path(os.environ.get("INDEX_DIRECTORY", "/home-index-root/files"))
INDEX_DIRECTORY.mkdir(parents=True, exist_ok=True)

METADATA_DIRECTORY = Path(
    os.environ.get("METADATA_DIRECTORY", "/home-index-root/metadata")
)
METADATA_DIRECTORY.mkdir(parents=True, exist_ok=True)

ARCHIVE_DIRECTORY = Path(
    os.environ.get("ARCHIVE_DIRECTORY", (INDEX_DIRECTORY / "archive").as_posix())
)
ARCHIVE_DIRECTORY.mkdir(parents=True, exist_ok=True)

APP_DIRECTORY = Path(os.environ.get("APP_DIRECTORY", "/home-index-root/app"))
APP_DIRECTORY.mkdir(parents=True, exist_ok=True)

RESERVED_FILES_DIRS = [METADATA_DIRECTORY, APP_DIRECTORY]


modules = {}
module_values = []
hellos = []
hello_versions = []
hello_versions_changed = False
hello_versions_file_path = Path("/home-index/hello_versions.json")

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


async def delete_docs_by_id(ids):
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


def path_from_relpath(relpath):
    return INDEX_DIRECTORY / relpath


def is_in_archive_dir(path):
    return ARCHIVE_DIRECTORY in path.parents


def write_doc_json(doc):
    path = METADATA_DIRECTORY / doc["paths"][0]
    if not path.exists():
        path.mkdir(parents=True)
    with (path / "document.json").open("w") as file:
        json.dump(doc, file, indent=4, separators=(", ", ": "))


def index_metadata():
    metadata_docs_by_hash = {}
    metadata_hashes_by_relpath = {}

    files_logger.info(f" * recursively walk metadata")
    file_paths = []
    for root, _, files in METADATA_DIRECTORY.walk(follow_symlinks=False):
        for f in files:
            if f == "document.json":
                file_paths.append(root / f)
                break

    def read_doc_json(doc_json_path):
        with doc_json_path.open("r") as file:
            return json.load(file)

    def handle_doc(doc):
        hash = doc["id"]
        if hash in metadata_docs_by_hash:
            return
        metadata_docs_by_hash[hash] = doc
        metadata_hashes_by_relpath.update(
            {relpath: [hash, mtime] for relpath, mtime in doc["paths"].items()}
        )

    if file_paths:
        files_logger.info(f" * check {len(file_paths)} file hashes")
        if MAX_HASH_WORKERS < 2:
            for fp in file_paths:
                handle_doc(read_doc_json(fp))
        else:
            with ProcessPoolExecutor(max_workers=MAX_HASH_WORKERS) as executor:
                for completed in as_completed(
                    executor.submit(read_doc_json, fp) for fp in file_paths
                ):
                    handle_doc(completed.result())

    return metadata_docs_by_hash, metadata_hashes_by_relpath


def index_files(metadata_docs_by_hash, metadata_hashes_by_relpath):
    files_docs_by_hash = {}
    files_hashes_by_relpath = {}

    files_logger.info(f" * recursively walk files")
    file_paths = []
    for root, _, files in INDEX_DIRECTORY.walk():
        if any(dir in root.parents for dir in RESERVED_FILES_DIRS):
            continue
        for f in files:
            file_paths.append(root / f)

    def determine_hash(path):
        relpath = path.relative_to(INDEX_DIRECTORY)
        hash = None
        if relpath in metadata_hashes_by_relpath:
            prev_hash, prev_mtime = metadata_hashes_by_relpath[relpath]
            is_mtime_changed = path.stat().st_mtime != prev_mtime
            if not is_mtime_changed:
                hash = prev_hash
        if not hash:
            hasher = xxhash.xxh64()
            with path.open("rb") as f:
                for chunk in iter(lambda: f.read(8192), b""):
                    hasher.update(chunk)
            hash = hasher.hexdigest()
        return path, hash

    def get_mime_type(file_path):
        mime = magic.Magic(mime=True)
        mime_type = mime.from_file(file_path)
        if mime_type == "application/octet-stream":
            mime_type, _ = mimetypes.guess_type(file_path)
            if mime_type is None:
                mime_type = "application/octet-stream"
        return mime_type

    def handle_hash_at_path(args):
        path, hash = args
        relpath = path.relative_to(INDEX_DIRECTORY)
        stat = path.stat()

        if hash in metadata_docs_by_hash:
            metadata_doc = copy.deepcopy(metadata_docs_by_hash[hash])
        if hash in files_docs_by_hash:
            files_doc = files_docs_by_hash[hash]

        doc = {}
        if metadata_doc and not files_doc:
            metadata_doc["paths"] = {
                relpath: mtime
                for relpath, mtime in files_doc["paths"].items()
                if is_in_archive_dir(path_from_relpath(relpath))
                and (
                    (not path_from_relpath(relpath).exists())
                    or (path_from_relpath(relpath).stat().st_mtime == mtime)
                )
            }
            doc = metadata_doc
        elif files_doc:
            doc = files_doc
        else:
            doc = {
                "id": hash,
                "paths": {},
                "mtime": stat.st_mtime,
                "size": stat.st_size,
                "type": get_mime_type(path),
                "status": initial_module_id,
            }

        doc["paths"][relpath] = stat.st_mtime
        doc["copies"] = len(doc["paths"])
        doc["is_archived"] = any(
            is_in_archive_dir(path_from_relpath(relpath))
            for relpath in doc["paths"].keys()
        )

        files_docs_by_hash[hash] = doc
        files_hashes_by_relpath[relpath] = hash

    if file_paths:
        files_logger.info(f" * check {len(file_paths)} file hashes")
        if MAX_HASH_WORKERS < 2:
            for fp in file_paths:
                handle_hash_at_path(determine_hash(fp))
        else:
            with ProcessPoolExecutor(max_workers=MAX_HASH_WORKERS) as executor:
                for completed in as_completed(
                    executor.submit(determine_hash, fp) for fp in file_paths
                ):
                    handle_hash_at_path(completed.result())

    return files_docs_by_hash, files_hashes_by_relpath


def update_metadata(
    metadata_docs_by_hash,
    metadata_hashes_by_relpath,
    files_docs_by_hash,
    files_hashes_by_relpath,
):
    files_logger.info(f" * check for deleted documents")
    deleted_hashes = list(
        set(metadata_docs_by_hash.keys()) - set(files_docs_by_hash.keys())
    )

    files_logger.info(f" * check for upserted documents")
    upserted_docs = [
        files_doc
        for hash, files_doc in files_docs_by_hash.items()
        if (not hash in metadata_docs_by_hash)
        or (metadata_docs_by_hash[hash]["paths"] != files_docs_by_hash[hash]["paths"])
    ]

    files_logger.info(f" * check for deleted file path")
    deleted_relpaths = list(
        set(metadata_hashes_by_relpath.keys()) - set(files_hashes_by_relpath.keys())
    )

    def handle_deleted_relpath(relpath):
        path = METADATA_DIRECTORY / relpath
        metadata_doc = metadata_docs_by_hash[metadata_hashes_by_relpath[relpath]]
        if metadata_doc["copies"] == 1:
            shutil.rmtree(path)
            return
        target_relpath = metadata_doc["paths"][0]
        if not relpath == target_relpath:
            path.unlink()
            return
        new_target_path = next(
            (
                METADATA_DIRECTORY / key
                for key in metadata_doc["paths"]
                if key in files_hashes_by_relpath
                and metadata_hashes_by_relpath[key] == files_hashes_by_relpath[key]
            ),
            None,
        )
        if new_target_path:
            new_target_path.unlink()
            target_relpath.rename(new_target_path)
        else:
            shutil.rmtree(path)

    def handle_upserted_doc(doc):
        target_path = METADATA_DIRECTORY / doc["paths"][0]
        if not target_path.exists():
            target_path.mkdir(parents=True)
        write_doc_json(doc)
        with (target_path / "version.json").open("w") as file:
            json.dump({"version": VERSION}, file, indent=4, separators=(", ", ": "))
        for relpath in doc["paths"]:
            copy_path = METADATA_DIRECTORY / relpath
            if copy_path.is_symlink():
                copy_path.unlink()
            relative_target = os.path.relpath(target_path, copy_path.parent)
            copy_path.symlink_to(relative_target, target_is_directory=True)

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

    if upserted_docs:
        files_logger.info(f" * upsert {len(upserted_docs)} metadata documents")
        if MAX_FILE_WORKERS < 2:
            for doc in upserted_docs:
                handle_upserted_doc(doc)
        else:
            with ThreadPoolExecutor(max_workers=MAX_FILE_WORKERS) as executor:
                for completed in as_completed(
                    executor.submit(handle_upserted_doc, doc) for doc in upserted_docs
                ):
                    completed.result()

    return upserted_docs, deleted_hashes


async def update_meilisearch(upserted_docs, deleted_hashes):
    if deleted_hashes:
        files_logger.info(f" * delete {len(deleted_hashes)} meilisearch documents")
        await delete_docs_by_id(deleted_hashes)
        await wait_for_meili_idle()
    if upserted_docs:
        files_logger.info(f" * upsert {len(upserted_docs)} meilisearch documents")
        await add_or_update_documents(upserted_docs)
        await wait_for_meili_idle()
    total_docs_in_meili = await get_document_count()
    files_logger.info(f"- {total_docs_in_meili} documents in meilisearch")


async def sync_documents():
    try:
        files_logger.info("index previously stored metadata")
        metadata_docs_by_hash, metadata_hashes_by_relpath = index_metadata()

        files_logger.info("index all files")
        files_docs_by_hash, files_hashes_by_relpath = index_files(
            metadata_docs_by_hash, metadata_hashes_by_relpath
        )

        files_logger.info("cross-index to update metadata")
        upserted_docs, deleted_hashes = update_metadata(
            metadata_docs_by_hash,
            metadata_hashes_by_relpath,
            files_docs_by_hash,
            files_hashes_by_relpath,
        )

        if upserted_docs or deleted_hashes:
            files_logger.info("commit changes to meilisearch")
            update_meilisearch(upserted_docs, deleted_hashes)
    except:
        files_logger.exception("sync failed")
        raise


# endregion
# region "run modules"


def file_relpath_from_meili_doc(document):
    return document["paths"][0]


def metadata_dir_relpath_from_doc(name, document):
    path = Path(METADATA_DIRECTORY / document["paths"][0] / name)
    path.mkdir(parents=True)
    return path.relative_to(METADATA_DIRECTORY).as_posix()


async def update_doc_from_module(document):
    file_relpath = file_relpath_from_meili_doc(document)

    status = "idle"
    for name, proxy in modules:
        metadata_dir_relpath = metadata_dir_relpath_from_doc(name, document)
        if proxy.check(file_relpath, document, metadata_dir_relpath):
            status = name
            break

    document["status"] = status
    write_doc_json(document)
    await add_or_update_document(document)
    return document


async def run_module(name, proxy):
    try:
        modules_logger.debug(f"{name} query documents list")
        documents = await get_all_pending_jobs(name)
        documents = sorted(documents, key=lambda x: x["mtime"], reverse=True)
        if documents:
            count = len(documents)
            modules_logger.info(f"{name} start for {count} documents")
            start_time = time.monotonic()
            for document in documents:
                try:
                    elapsed_time = time.monotonic() - start_time
                    if elapsed_time > ALLOWED_TIME_PER_MODULE:
                        modules_logger.info(f"{name} post-poned {count} documents")
                        return True
                    file_relpath = file_relpath_from_meili_doc(document)
                    metadata_dir_relpath = metadata_dir_relpath_from_doc(name, document)
                    document = await update_doc_from_module(document)
                    if document["status"] == name:
                        document = proxy.run(
                            file_relpath, document, metadata_dir_relpath
                        )
                        await update_doc_from_module(document)
                except:
                    modules_logger.exception(f'{name} "{document}" failed')
                count = count - 1
        modules_logger.info(f"{name} ran for all documents")
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
