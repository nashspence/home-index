from __future__ import annotations

import asyncio
import json
import logging
import logging.handlers
import os
import time
from pathlib import Path
from typing import Any, Mapping, Callable, TypeVar, cast, TYPE_CHECKING
from xmlrpc.client import Fault, ServerProxy

from features.F2.metadata_store import (
    by_id_directory,
    metadata_directory,
    write_doc_json,
)
from features.F3.archive import doc_is_online, update_archive_flags

if TYPE_CHECKING:  # pragma: no cover
    from typing import Any

    hi: Any
else:
    import main as hi

LOGGING_LEVEL = os.environ.get("LOGGING_LEVEL", "INFO")
LOGGING_MAX_BYTES = int(os.environ.get("LOGGING_MAX_BYTES", 5_000_000))
LOGGING_BACKUP_COUNT = int(os.environ.get("LOGGING_BACKUP_COUNT", 10))
LOGGING_DIRECTORY = os.environ.get("LOGGING_DIRECTORY", "/home-index")
os.makedirs(LOGGING_DIRECTORY, exist_ok=True)

modules_logger = logging.getLogger("home-index-modules")
modules_logger.setLevel(LOGGING_LEVEL)
_file_handler = logging.handlers.RotatingFileHandler(
    os.path.join(LOGGING_DIRECTORY, "modules.log"),
    maxBytes=LOGGING_MAX_BYTES,
    backupCount=LOGGING_BACKUP_COUNT,
)
_file_handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
modules_logger.addHandler(_file_handler)

DEBUG = str(os.environ.get("DEBUG", "False")) == "True"
MODULES_MAX_SECONDS = int(os.environ.get("MODULES_MAX_SECONDS", 5 if DEBUG else 300))
MODULES_SLEEP_SECONDS = int(
    os.environ.get(
        "MODULES_SLEEP_SECONDS",
        os.environ.get("MODULES_MAX_SECONDS", 1 if DEBUG else 1800),
    )
)

MODULES = os.environ.get("MODULES", "")
RETRY_UNTIL_READY_SECONDS = int(os.environ.get("RETRY_UNTIL_READY_SECONDS", "60"))
HELLO_RETRY_SECONDS = int(
    os.environ.get("MODULES_HELLO_RETRY_SECONDS", RETRY_UNTIL_READY_SECONDS)
)
CHECK_RETRY_SECONDS = int(
    os.environ.get("MODULES_CHECK_RETRY_SECONDS", RETRY_UNTIL_READY_SECONDS)
)
POST_RUN_RETRY_SECONDS = int(
    os.environ.get("MODULES_POST_RUN_RETRY_SECONDS", RETRY_UNTIL_READY_SECONDS)
)

hellos: list[dict[str, Any]] = []
module_values: list[dict[str, Any]] = []
modules: dict[str, dict[str, Any]] = {}
hello_versions: list[list[Any]] = []

hello_versions_file_path = Path(
    os.environ.get("HELLO_VERSIONS_FILE_PATH", "/home-index/hello_versions.json")
)


T = TypeVar("T")


def retry_until_ready(
    fn: Callable[[], T], msg: str, seconds: int = RETRY_UNTIL_READY_SECONDS
) -> T:
    for attempt in range(seconds):
        try:
            return fn()
        except Exception as e:
            if attempt < seconds - 1:
                time.sleep(1)
            else:
                raise RuntimeError(msg) from e
    raise RuntimeError(msg)


def setup_modules() -> tuple[
    dict[str, dict[str, Any]],
    list[dict[str, Any]],
    list[dict[str, Any]],
    list[list[Any]],
]:
    hellos_local: list[dict[str, Any]] = []
    module_values_local: list[dict[str, Any]] = []
    modules_local: dict[str, dict[str, Any]] = {}
    hello_versions_local: list[list[Any]] = []
    if MODULES:
        for module_host in MODULES.split(","):
            module_host = module_host.strip()
            proxy = ServerProxy(module_host)
            hello = retry_until_ready(
                lambda: json.loads(cast(str, proxy.hello())),
                f"Failed to get 'hello' from {module_host} many retries",
                seconds=HELLO_RETRY_SECONDS,
            )
            name = hello["name"]
            if name in modules_local:
                raise ValueError(
                    f"multiple modules found with name {name}, this must be unique"
                )
            version = hello["version"]
            hellos_local.append(hello)
            hello_versions_local.append([name, version])
            modules_local[name] = {"name": name, "proxy": proxy, "host": module_host}
            module_values_local.append(modules_local[name])
    return modules_local, module_values_local, hellos_local, hello_versions_local


def set_global_modules() -> None:
    global hellos, module_values, modules, hello_versions
    modules, module_values, hellos, hello_versions = setup_modules()


set_global_modules()


def get_is_modules_changed() -> bool:
    if not hello_versions_file_path.exists():
        return True
    with hello_versions_file_path.open("r") as file:
        hello_versions_json = json.load(file)
    known = cast(list[list[Any]], hello_versions_json.get("hello_versions", ""))
    return hello_versions != known


is_modules_changed = get_is_modules_changed()


def save_modules_state() -> None:
    hello_versions_file_path.parent.mkdir(parents=True, exist_ok=True)
    with hello_versions_file_path.open("w") as file:
        json.dump({"hello_versions": hello_versions}, file)


def file_relpath_from_meili_doc(document: Mapping[str, Any]) -> str:
    paths = cast(Mapping[str, Any], document["paths"])
    return next(iter(paths.keys()))


def metadata_dir_relpath_from_doc(name: str, document: Mapping[str, Any]) -> Path:
    path = Path(by_id_directory()) / cast(str, document["id"]) / name
    path.mkdir(parents=True, exist_ok=True)
    return path.relative_to(metadata_directory())


async def update_doc_from_module(document: dict[str, Any]) -> dict[str, Any]:

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
                    f"failed to contact {module['host']} after module run",
                    seconds=POST_RUN_RETRY_SECONDS,
                )
            )
        )
        if document["id"] in claimed:
            next_module_name = module["name"]
            break
    document["next"] = next_module_name
    update_archive_flags(document)
    write_doc_json(document)
    await hi.add_or_update_document(document)
    return document


def set_next_modules(files_docs_by_hash: dict[str, dict[str, Any]]) -> None:
    needs_update = {
        id: doc for id, doc in files_docs_by_hash.items() if doc_is_online(doc)
    }
    for module in module_values:
        claimed = set(
            json.loads(
                retry_until_ready(
                    lambda: module["proxy"].check(
                        json.dumps(list(needs_update.values()))
                    ),
                    f"failed to contact {module['host']} during sync",
                    seconds=CHECK_RETRY_SECONDS,
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


async def run_module(name: str, proxy: ServerProxy) -> bool:

    try:
        documents = await hi.get_all_pending_jobs(name)
        documents = sorted(documents, key=lambda x: x["mtime"], reverse=True)
        if documents:
            modules_logger.info("-----------------------------------------------")
            modules_logger.info(f'start "{name}"')
            count = len(documents)
            modules_logger.info(" * call load")
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
                        result = json.loads(cast(str, proxy.run(json.dumps(document))))
                        if isinstance(result, dict) and "document" in result:
                            chunk_docs = result.get("chunk_docs", [])
                            delete_chunk_ids = result.get("delete_chunk_ids", [])
                            document = result["document"]
                        else:
                            document = result
                            chunk_docs = []
                            delete_chunk_ids = []
                        if chunk_docs:
                            texts = []
                            for chunk in chunk_docs:
                                if "text" in chunk:
                                    chunk["text"] = "passage: " + chunk["text"]
                                    texts.append(chunk["text"])
                                chunk.setdefault("module", name)
                            vectors = hi.embed_texts(texts)
                            for chunk, vec in zip(chunk_docs, vectors):
                                chunk["_vector"] = vec
                            await hi.add_or_update_chunk_documents(chunk_docs)
                        if delete_chunk_ids:
                            await hi.delete_chunk_docs_by_id(delete_chunk_ids)
                        await hi.update_doc_from_module(document)
                    except Fault as e:
                        modules_logger.warning(f'   x "{relpath}": {str(e)}')
                    except Exception as e:  # pragma: no cover - unexpected
                        modules_logger.warning(f'   x "{relpath}"')
                        raise e
                    count -= 1
                modules_logger.info("   * done")
                return False
            except Exception as e:
                modules_logger.warning(f" x failed: {str(e)}")
                return True
            finally:
                modules_logger.info(" * call unload")
                proxy.unload()
                modules_logger.info(" * wait for meilisearch")
                await hi.wait_for_meili_idle()
                modules_logger.info(" * done")
        else:
            return False
    except Exception as e:  # pragma: no cover - unexpected
        modules_logger.warning(f"failed: {str(e)}")
        return True


async def run_modules() -> None:
    modules_logger.info("")
    modules_logger.info("start modules processing")
    for index, module in enumerate(module_values):
        modules_logger.info(f" {index + 1}. {module['name']}")
    while True:
        run_again = False
        for module in module_values:
            module_did_not_finish = await run_module(module["name"], module["proxy"])
            run_again = run_again or module_did_not_finish
        if not run_again:
            await asyncio.sleep(MODULES_SLEEP_SECONDS)
