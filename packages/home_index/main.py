# region "debugpy"


import os

if str(os.environ.get("DEBUG", "False")) == "True":
    import debugpy

    debugpy.listen(("0.0.0.0", 5678))

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

modules_logger = logging.getLogger("home-index-modules")
modules_logger.setLevel(LOGGING_LEVEL)
file_handler = logging.handlers.RotatingFileHandler(
    "/home-index/modules.log",
    maxBytes=LOGGING_MAX_BYTES,
    backupCount=LOGGING_BACKUP_COUNT,
)
file_handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
modules_logger.addHandler(file_handler)

files_logger = logging.getLogger("home-index-files")
files_logger.setLevel(LOGGING_LEVEL)
file_handler = logging.handlers.RotatingFileHandler(
    "/home-index/files.log",
    maxBytes=LOGGING_MAX_BYTES,
    backupCount=LOGGING_BACKUP_COUNT,
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
import math
from xmlrpc.client import ServerProxy, Fault
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from multiprocessing import Process
from itertools import chain
from meilisearch_python_sdk import AsyncClient
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor, as_completed
from multiprocessing import Manager


# endregion
# region "config"


VERSION = 1
DEBUG = str(os.environ.get("DEBUG", "False")) == "True"

MODULES_MAX_SECONDS = int(
    os.environ.get(
        "MODULES_MAX_SECONDS",
        5 if DEBUG else 300,
    )
)
MODULES_SLEEP_SECONDS = int(
    os.environ.get(
        "MODULES_SLEEP_SECONDS",
        os.environ.get(
            "MODULES_MAX_SECONDS",
            1 if DEBUG else 1800,
        ),
    )
)

MEILISEARCH_BATCH_SIZE = int(os.environ.get("MEILISEARCH_BATCH_SIZE", "10000"))
MEILISEARCH_HOST = os.environ.get("MEILISEARCH_HOST", "http://localhost:7700")
MEILISEARCH_INDEX_NAME = os.environ.get("MEILISEARCH_INDEX_NAME", "files")

CPU_COUNT = os.cpu_count()
MAX_HASH_WORKERS = int(os.environ.get("MAX_HASH_WORKERS", CPU_COUNT / 2))
MAX_FILE_WORKERS = int(os.environ.get("MAX_FILE_WORKERS", CPU_COUNT / 2))

INDEX_DIRECTORY = Path(os.environ.get("INDEX_DIRECTORY", "/files"))
INDEX_DIRECTORY.mkdir(parents=True, exist_ok=True)

METADATA_DIRECTORY = Path(os.environ.get("METADATA_DIRECTORY", "/files/metadata"))
METADATA_DIRECTORY.mkdir(parents=True, exist_ok=True)
BY_ID_DIRECTORY = Path(
    os.environ.get("BY_ID_DIRECTORY", str(METADATA_DIRECTORY / "by-id"))
)
BY_ID_DIRECTORY.mkdir(parents=True, exist_ok=True)
BY_PATH_DIRECTORY = Path(
    os.environ.get("BY_PATH_DIRECTORY", str(METADATA_DIRECTORY / "by-path"))
)
BY_PATH_DIRECTORY.mkdir(parents=True, exist_ok=True)

ARCHIVE_DIRECTORY = Path(
    os.environ.get("ARCHIVE_DIRECTORY", (INDEX_DIRECTORY / "archive").as_posix())
)
ARCHIVE_DIRECTORY.mkdir(parents=True, exist_ok=True)

RESERVED_FILES_DIRS = [METADATA_DIRECTORY]


MODULES = os.environ.get("MODULES", "")


def retry_until_ready(fn, msg, seconds=60):
    for attempt in range(seconds):
        try:
            return fn()
        except Exception as e:
            if attempt < 59:
                time.sleep(1)
            else:
                raise RuntimeError(msg) from e


def setup_modules():
    hellos = []
    module_values = []
    modules = {}
    hello_versions = []

    if MODULES:
        for module_host in MODULES.split(","):
            module_host = module_host.strip()
            proxy = ServerProxy(module_host)

            hello = retry_until_ready(
                lambda: json.loads(proxy.hello()),
                f"Failed to get 'hello' from {module_host} many retries",
            )

            try:
                name = hello["name"]
            except KeyError:
                raise ValueError(f'{module_host} did not return "name" on hello')

            if name in modules:
                raise ValueError(
                    f"multiple modules found with name {name}, this must be unique"
                )

            try:
                version = hello["version"]
            except KeyError:
                raise ValueError(f'{module_host} did not return "version" on hello')

            hellos.append(hello)
            hello_versions.append([name, version])

            modules[name] = {"name": name, "proxy": proxy, "host": module_host}
            module_values.append(modules[name])

    return modules, module_values, hellos, hello_versions


hellos = []
module_values = []
modules = {}
hello_versions = []


def set_global_modules():
    global hellos, module_values, modules, hello_versions
    m, mv, h, hv = setup_modules()
    modules = m
    module_values = mv
    hellos = h
    hello_versions = hv


set_global_modules()


hello_versions_changed = False
hello_versions_file_path = Path("/home-index/hello_versions.json")

hello_versions_json = {}
if hello_versions_file_path.exists():
    with hello_versions_file_path.open("r") as file:
        hello_versions_json = json.load(file)

known_hello_versions = hello_versions_json.get("hello_versions", "")
hello_versions_changed = hello_versions != known_hello_versions


def get_is_modules_changed():
    if not hello_versions_file_path.exists():
        return True
    with hello_versions_file_path.open("r") as file:
        hello_versions_json = json.load(file)
    known_hello_versions = hello_versions_json.get("hello_versions", "")
    return hello_versions != known_hello_versions


is_modules_changed = get_is_modules_changed()


def save_modules_state():
    global is_modules_changed
    hello_versions_file_path.parent.mkdir(parents=True, exist_ok=True)
    with hello_versions_file_path.open("w") as file:
        json.dump({"hello_versions": hello_versions}, file)
    is_modules_changed = False


def parse_cron_env(env_var="CRON_EXPRESSION", default="0 3 * * *"):
    cron_expression = os.getenv(env_var, default)
    parts = cron_expression.split()
    if len(parts) != 5:
        raise ValueError(
            f"Invalid cron expression in {env_var}: '{cron_expression}'. Must have 5 fields."
        )
    return {
        "minute": parts[0],
        "hour": parts[1],
        "day": parts[2],
        "month": parts[3],
        "day_of_week": parts[4],
    }


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
        "mtime",
        "paths",
        "size",
        "next",
        "type",
    ] + list(chain(*[hello["filterable_attributes"] for hello in hellos]))

    try:
        logging.debug(f"meili update index attrs")
        await index.update_filterable_attributes(filterable_attributes)
        await index.update_sortable_attributes(
            [
                "mtime",
                "paths",
                "size",
                "next",
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
            logging.debug(f'index.update_documents "{next(iter(doc["paths"]))}" start')
            await index.update_documents([doc])
            logging.debug(f'index.update_documents "{next(iter(doc["paths"]))}" done')
        except Exception:
            logging.exception(
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
        logging.error(f"failed to get pending jobs from meilisearch: {e}")
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
    path = BY_ID_DIRECTORY / doc["id"]
    if not path.exists():
        path.mkdir(parents=True, exist_ok=True)
    with (path / "document.json").open("w") as file:
        json.dump(doc, file, indent=4, separators=(", ", ": "))


def truncate_mtime(st_mtime):
    return math.floor(st_mtime * 10000) / 10000


def is_apple_double(file_path):
    try:
        with Path(file_path).open("rb") as file:
            return file.read(4) == b"\x00\x05\x16\x07"
    except:
        return False


def get_mime_type(file_path):
    mime = magic.Magic(mime=True)
    mime_type = mime.from_file(file_path)
    if mime_type == "application/octet-stream":
        if is_apple_double(file_path):
            return "multipart/appledouble"
        mime_type, _ = mimetypes.guess_type(file_path, strict=False)
        if mime_type is None:
            mime_type = "application/octet-stream"
    return mime_type


def determine_hash(path, metadata_docs_by_hash, metadata_hashes_by_relpath):
    relpath = str(path.relative_to(INDEX_DIRECTORY).as_posix())
    hash = None
    stat = path.stat()
    if relpath in metadata_hashes_by_relpath:
        prev_hash = metadata_hashes_by_relpath[relpath]
        prev_mtime = metadata_docs_by_hash[prev_hash]["paths"][relpath]
        is_mtime_changed = truncate_mtime(stat.st_mtime) != prev_mtime
        if not is_mtime_changed:
            hash = prev_hash
    if not hash:
        hasher = xxhash.xxh64()
        with path.open("rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                hasher.update(chunk)
        hash = hasher.hexdigest()
    mime_type = get_mime_type(path)
    return path, hash, stat, mime_type


def set_next_modules(files_docs_by_hash):
    needs_update = {id: doc for id, doc in files_docs_by_hash.items()}
    for module in module_values:
        claimed = set(
            json.loads(
                retry_until_ready(
                    lambda: module["proxy"].check(
                        json.dumps(list(needs_update.values()))
                    ),
                    f"failed to contact {module["host"]} during sync",
                )
            )
        )
        for id in claimed:
            doc = needs_update.pop(id)
            doc["next"] = module["name"]
        if not needs_update:
            break
    for id, doc in needs_update.items():
        doc["next"] = ""


def index_metadata():
    metadata_docs_by_hash = {}
    metadata_hashes_by_relpath = {}
    unmounted_archive_docs_by_hash = {}
    unmounted_archive_hashes_by_relpath = {}

    files_logger.info(f" * iterate metadata by-id")
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
        hash = doc["id"]
        if hash in metadata_docs_by_hash:
            return
        metadata_docs_by_hash[hash] = doc

        if all(
            is_in_archive_dir(path_from_relpath(relpath))
            and not path_from_relpath(relpath).exists()
            for relpath in doc["paths"].keys()
        ):
            doc_copy = copy.deepcopy(doc)
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
    )


def index_files(
    metadata_docs_by_hash,
    metadata_hashes_by_relpath,
    unmounted_archive_docs_by_hash,
    unmounted_archive_hashes_by_relpath,
):
    files_docs_by_hash = unmounted_archive_docs_by_hash
    files_hashes_by_relpath = unmounted_archive_hashes_by_relpath

    files_logger.info(f" * recursively walk files")
    file_paths = []
    for root, _, files in INDEX_DIRECTORY.walk():
        if any(dir in root.parents for dir in RESERVED_FILES_DIRS):
            continue
        for f in files:
            file_paths.append(root / f)

    def handle_hash_at_path(args):
        path, hash, stat, mime_type = args
        relpath = str(path.relative_to(INDEX_DIRECTORY))

        metadata_doc = files_doc = None
        if hash in metadata_docs_by_hash:
            metadata_doc = copy.deepcopy(metadata_docs_by_hash[hash])
        if hash in files_docs_by_hash:
            files_doc = files_docs_by_hash[hash]

        doc = {}
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
                "id": hash,
                "paths": {},
                "mtime": truncate_mtime(stat.st_mtime),
                "size": stat.st_size,
                "type": mime_type,
            }

        doc["type"] = mime_type
        doc["paths"][relpath] = truncate_mtime(stat.st_mtime)
        doc["copies"] = len(doc["paths"])
        doc["mtime"] = max(doc["paths"].values())

        files_docs_by_hash[hash] = doc
        files_hashes_by_relpath[relpath] = hash

    if file_paths:
        files_logger.info(f" * check {len(file_paths)} file hashes")
        if MAX_HASH_WORKERS < 2:
            for fp in file_paths:
                handle_hash_at_path(
                    determine_hash(
                        fp, metadata_docs_by_hash, metadata_hashes_by_relpath
                    )
                )
        else:
            manager = Manager()
            shared_metadata_docs_by_hash = manager.dict(metadata_docs_by_hash)
            shared_metadata_hashes_by_relpath = manager.dict(metadata_hashes_by_relpath)

            with ProcessPoolExecutor(max_workers=MAX_HASH_WORKERS) as executor:
                for completed in as_completed(
                    executor.submit(
                        determine_hash,
                        fp,
                        shared_metadata_docs_by_hash,
                        shared_metadata_hashes_by_relpath,
                    )
                    for fp in file_paths
                ):
                    handle_hash_at_path(completed.result())

    if files_docs_by_hash:
        files_logger.info(f" * set next modules")
        set_next_modules(files_docs_by_hash)

    return files_docs_by_hash, files_hashes_by_relpath


def update_metadata(
    metadata_docs_by_hash,
    metadata_hashes_by_relpath,
    files_docs_by_hash,
    files_hashes_by_relpath,
):
    files_logger.info(f" * check for upserted documents")
    upserted_docs_by_hash = {
        hash: files_doc
        for hash, files_doc in files_docs_by_hash.items()
        if (not hash in metadata_docs_by_hash)
        or (metadata_docs_by_hash[hash]["paths"] != files_docs_by_hash[hash]["paths"])
        or (
            metadata_docs_by_hash[hash].get("next")
            != files_docs_by_hash[hash].get("next")
        )
    }

    files_logger.info(f" * check for deleted file path")
    deleted_relpaths = set(metadata_hashes_by_relpath.keys()) - set(
        files_hashes_by_relpath.keys()
    )

    def handle_deleted_relpath(relpath):
        metadata_doc = metadata_docs_by_hash[metadata_hashes_by_relpath[relpath]]
        by_id_path = BY_ID_DIRECTORY / metadata_doc["id"]
        by_path_path = BY_PATH_DIRECTORY / relpath
        if not metadata_doc["id"] in files_docs_by_hash and by_id_path.exists():
            shutil.rmtree(by_id_path)
        if by_path_path.is_symlink():
            by_path_path.unlink()
        if (
            by_path_path.parent
            and by_path_path.parent != BY_PATH_DIRECTORY
            and by_path_path.parent.exists()
        ):
            total_count = len(list(by_path_path.parent.iterdir()))
            if total_count == 0:
                shutil.rmtree(by_path_path.parent)

    def handle_upserted_doc(doc):
        by_id_path = BY_ID_DIRECTORY / doc["id"]
        write_doc_json(doc)
        for relpath in doc["paths"].keys():
            by_path_path = BY_PATH_DIRECTORY / relpath
            by_path_path.parent.mkdir(parents=True, exist_ok=True)
            if by_path_path.is_symlink():
                by_path_path.unlink()
            relative_target = os.path.relpath(by_id_path, by_path_path.parent)
            by_path_path.symlink_to(relative_target, target_is_directory=True)

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
    files_logger.info(f" * get all meilisearch documents")
    all_meili_docs = await get_all_documents()
    meili_hashes = {doc["id"] for doc in all_meili_docs}

    files_logger.info(f" * check for redundant meilisearch documents")
    deleted_hashes = meili_hashes - set(files_docs_by_hash.keys())

    files_logger.info(f" * check for missing meilisearch documents")
    missing_meili_hashes = set(files_docs_by_hash.keys()) - meili_hashes
    upserted_docs_by_hash.update(
        {hash: files_docs_by_hash[hash] for hash in missing_meili_hashes}
    )

    if deleted_hashes:
        files_logger.info(f" * delete {len(deleted_hashes)} meilisearch documents")
        await delete_docs_by_id(list(deleted_hashes))
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
        files_logger.info(f"---------------------------------------------------")
        files_logger.info(f"start file sync")
        files_logger.info("index previously stored metadata")
        (
            metadata_docs_by_hash,
            metadata_hashes_by_relpath,
            unmounted_archive_docs_by_hash,
            unmounted_archive_hashes_by_relpath,
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

        files_logger.info("commit changes to meilisearch")
        await update_meilisearch(upserted_docs_by_hash, files_docs_by_hash)
    except:
        files_logger.exception("sync failed")
        raise


# endregion
# region "run modules"


def file_relpath_from_meili_doc(document):
    return next(iter(document["paths"].keys()))


def metadata_dir_relpath_from_doc(name, document):
    path = Path(BY_ID_DIRECTORY / document["id"] / name)
    path.mkdir(parents=True, exist_ok=True)
    return path.relative_to(METADATA_DIRECTORY)


async def update_doc_from_module(document):
    next_module_name = ""
    found_previous_next = False
    for module in module_values:
        if not found_previous_next:
            if module["name"] == document["next"]:
                found_previous_next = True
            continue

        claimed = set(
            json.loads(
                retry_until_ready(
                    lambda: module["proxy"].check(json.dumps([document])),
                    f"failed to contact {module["host"]} after module run",
                )
            )
        )

        if document["id"] in claimed:
            next_module_name = module["name"]
            break
    document["next"] = next_module_name
    write_doc_json(document)
    await add_or_update_document(document)
    return document


async def run_module(name, proxy):
    try:
        documents = await get_all_pending_jobs(name)
        documents = sorted(documents, key=lambda x: x["mtime"], reverse=True)
        if documents:
            modules_logger.info(f"---------------------------------------------------")
            modules_logger.info(f'start "{name}"')
            count = len(documents)
            modules_logger.info(f" * call load")
            proxy.load()
            modules_logger.info(f" * run for {count}")
            try:
                start_time = time.monotonic()
                for document in documents:
                    relpath = file_relpath_from_meili_doc(document)
                    try:
                        elapsed_time = time.monotonic() - start_time
                        if elapsed_time > MODULES_MAX_SECONDS:
                            modules_logger.info(
                                f"   * time up after {len(documents) - count} ({count} remain)"
                            )
                            return True
                        document = json.loads(proxy.run(json.dumps(document)))
                        await update_doc_from_module(document)
                    except Fault as e:
                        modules_logger.warning(f'   x "{relpath}": {str(e)}')
                    except Exception as e:
                        modules_logger.warning(f'   x "{relpath}"')
                        raise e
                    count = count - 1
                modules_logger.info(f"   * done")
                return False
            except Exception as e:
                modules_logger.warning(f" x failed: {str(e)}")
                return True
            finally:
                modules_logger.info(f" * call unload")
                proxy.unload()
                modules_logger.info(f" * wait for meilisearch")
                await wait_for_meili_idle()
                modules_logger.info(f" * done")
    except Exception as e:
        modules_logger.warning(f"failed: {str(e)}")
        return True


async def run_modules():
    modules_logger.info(f"")
    modules_logger.info(f"start modules processing")
    for index, module in enumerate(module_values):
        modules_logger.info(f" {index + 1}. {module["name"]}")

    while True:
        run_again = False
        for module in module_values:
            module_did_not_finish = await run_module(module["name"], module["proxy"])
            run_again = run_again or module_did_not_finish
        if not run_again:
            await asyncio.sleep(MODULES_SLEEP_SECONDS)


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
    await init_meili()
    scheduler = BackgroundScheduler()

    scheduler.add_job(
        run_in_process,
        (IntervalTrigger(seconds=60) if DEBUG else CronTrigger(**parse_cron_env())),
        args=[init_meili_and_sync],
        max_instances=1,
    )

    if is_modules_changed:
        modules_logger.info(f"*** perform sync on MODULES changed")
        await init_meili_and_sync()
        save_modules_state()

    scheduler.start()
    await run_modules()


if __name__ == "__main__":
    asyncio.run(main())


# endregion
