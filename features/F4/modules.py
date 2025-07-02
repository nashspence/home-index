from __future__ import annotations

import asyncio
import json
import logging
import logging.handlers
import os
import time
from urllib.parse import urlparse
from pathlib import Path
import importlib
import sys
from typing import Any, Callable, Mapping, MutableMapping, TypeVar, cast
from features.F3.archive import doc_is_online, update_archive_flags

try:
    import redis
except Exception:  # pragma: no cover - redis optional for tests
    redis = None

try:
    import yaml
except Exception:  # pragma: no cover - yaml optional for tests
    yaml = None


def metadata_directory() -> Path:
    """Return the root metadata directory."""
    return Path(os.environ.get("METADATA_DIRECTORY", "/files/metadata"))


def by_id_directory() -> Path:
    """Return the directory where metadata is stored by file ID."""
    return Path(os.environ.get("BY_ID_DIRECTORY", str(metadata_directory() / "by-id")))


def ensure_directories() -> None:
    for path in [metadata_directory(), by_id_directory()]:
        path.mkdir(parents=True, exist_ok=True)


def _get_hi() -> Any:
    try:
        from home_index import main as hi
    except Exception:  # pragma: no cover - compatibility
        hi = sys.modules.get("main")
        if hi is None:
            hi = sys.modules.get("__main__")
        if hi is None:
            hi = importlib.import_module("main")
    return hi


def write_doc_json(doc: MutableMapping[str, Any]) -> None:
    ensure_directories()
    target_dir = by_id_directory() / str(doc["id"])
    target_dir.mkdir(parents=True, exist_ok=True)
    with (target_dir / "document.json").open("w") as f:
        json.dump(doc, f, indent=4, separators=(", ", ": "))


__all__ = [
    "setup_modules",
    "set_global_modules",
    "is_modules_changed",
    "save_modules_state",
]

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
REDIS_HOST = os.environ.get("REDIS_HOST", "redis")
RETRY_UNTIL_READY_SECONDS = int(os.environ.get("RETRY_UNTIL_READY_SECONDS", "60"))
DONE_QUEUE = "modules:done"
TIMEOUT_SET = "timeouts"


def make_redis_client() -> redis.Redis:
    host = REDIS_HOST
    if "://" in host:
        parsed = urlparse(host)
        return redis.Redis(
            host=parsed.hostname or host,
            port=parsed.port or 6379,
            decode_responses=True,
        )
    return redis.Redis(host=host, decode_responses=True)


module_configs: list[dict[str, Any]] = []
module_values: list[dict[str, Any]] = []
modules: dict[str, dict[str, Any]] = {}
modules_config_file_path = Path(
    os.environ.get("MODULES_CONFIG_FILE_PATH", "/home-index/modules_config.json")
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


def setup_modules() -> (
    tuple[dict[str, dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]
):
    configs_local: list[dict[str, Any]] = []
    module_values_local: list[dict[str, Any]] = []
    modules_local: dict[str, dict[str, Any]] = {}
    if MODULES:
        try:
            configs_local = cast(list[dict[str, Any]], yaml.safe_load(MODULES)) or []
        except Exception:
            configs_local = []
        for cfg in configs_local:
            name = cfg["name"]
            modules_local[name] = cfg
            module_values_local.append(cfg)
    return modules_local, module_values_local, configs_local


def set_global_modules() -> None:
    global module_configs, module_values, modules
    modules, module_values, module_configs = setup_modules()


set_global_modules()


def get_is_modules_changed() -> bool:
    if not modules_config_file_path.exists():
        return True
    with modules_config_file_path.open("r") as file:
        config_json = json.load(file)
    known = cast(list[dict[str, Any]], config_json.get("modules", []))
    return module_configs != known


is_modules_changed = get_is_modules_changed()


def save_modules_state() -> None:
    modules_config_file_path.parent.mkdir(parents=True, exist_ok=True)
    with modules_config_file_path.open("w") as file:
        json.dump({"modules": module_configs}, file)


def file_relpath_from_meili_doc(document: Mapping[str, Any]) -> str:
    paths = cast(Mapping[str, Any], document["paths"])
    return next(iter(paths.keys()))


def metadata_dir_relpath_from_doc(name: str, document: Mapping[str, Any]) -> Path:
    path = Path(by_id_directory()) / cast(str, document["id"]) / name
    path.mkdir(parents=True, exist_ok=True)
    return path.relative_to(metadata_directory())


async def update_doc_from_module(document: dict[str, Any]) -> dict[str, Any]:
    hi = cast(Any, _get_hi())

    next_name = ""
    if document["next"] in modules:
        idx = module_values.index(modules[document["next"]])
        if idx + 1 < len(module_values):
            next_name = module_values[idx + 1]["name"]
    document["next"] = next_name
    update_archive_flags(document)
    write_doc_json(document)
    await hi.add_or_update_document(document)
    return document


def set_next_modules(files_docs_by_hash: dict[str, dict[str, Any]]) -> None:
    if not module_values:
        return
    for doc in files_docs_by_hash.values():
        if doc_is_online(doc):
            doc["next"] = module_values[0]["name"]
        else:
            doc["next"] = ""


async def process_done_queue(client: redis.Redis, hi: Any) -> bool:
    processed = False
    while True:
        result_json = client.lpop(DONE_QUEUE)
        if not result_json:
            break
        processed = True
        result = json.loads(result_json)
        name = result.get("module", "")
        if isinstance(result, dict) and "document" in result:
            chunk_docs = result.get("chunk_docs", [])
            delete_chunk_ids = result.get("delete_chunk_ids", [])
            document = result["document"]
        else:
            document = result
            chunk_docs = []
            delete_chunk_ids = []
        if chunk_docs:
            for chunk in chunk_docs:
                chunk.setdefault("module", name)
            await hi.add_or_update_chunk_documents(chunk_docs)
        if delete_chunk_ids:
            await hi.delete_chunk_docs_by_id(delete_chunk_ids)
        await hi.update_doc_from_module(document)
    return processed


def process_timeouts(client: redis.Redis) -> bool:
    """Requeue jobs whose timeout expired.

    Uses ``ZPOPMIN`` so each expiration is removed atomically before being
    processed. If the popped job hasn't expired yet it is added back to the
    ``TIMEOUT_SET``.
    """

    processed = False
    while True:
        items = client.zpopmin(TIMEOUT_SET)
        if not items:
            break
        member, score = items[0]
        now = time.time()
        if score > now:
            client.zadd(TIMEOUT_SET, {member: score})
            break
        data = json.loads(member)
        queue = data.get("q")
        doc_json = data.get("d")
        if queue and doc_json:
            with client.pipeline() as pipe:
                pipe.lrem(f"{queue}:processing", 0, doc_json)
                pipe.lpush(queue, doc_json)
                pipe.execute()
            processed = True
    return processed


async def service_module_queue(name: str) -> bool:
    try:
        from home_index import main as hi
    except Exception:  # pragma: no cover - compatibility
        hi = sys.modules.get("main")
        if hi is None:
            hi = sys.modules.get("__main__")
        if hi is None:
            hi = importlib.import_module("main")
    hi = cast(Any, hi)

    try:
        client = make_redis_client()

        processed = False

        documents = await hi.get_all_pending_jobs(name)
        check_tasks = set(client.lrange(f"{name}:check", 0, -1))
        run_tasks = set(client.lrange(f"{name}:run", 0, -1))
        processing_check = set(client.lrange(f"{name}:check:processing", 0, -1))
        processing_run = set(client.lrange(f"{name}:run:processing", 0, -1))
        for document in sorted(documents, key=lambda x: x["mtime"], reverse=True):
            doc_json = json.dumps(document)
            if (
                doc_json not in check_tasks
                and doc_json not in run_tasks
                and doc_json not in processing_check
                and doc_json not in processing_run
            ):
                client.rpush(f"{name}:check", doc_json)
                processed = True

        if processed:
            await hi.wait_for_meili_idle()

        return processed
    except Exception as e:  # pragma: no cover - unexpected
        modules_logger.warning(f"failed: {str(e)}")
        return True


async def service_module_queues() -> None:
    modules_logger.info("")
    modules_logger.info("start modules processing")
    for index, module in enumerate(module_values):
        modules_logger.info(f" {index + 1}. {module['name']}")
    client = make_redis_client()
    while True:
        processed = False
        if process_timeouts(client):
            processed = True
        if await process_done_queue(client, _get_hi()):
            processed = True
        tasks = [service_module_queue(module["name"]) for module in module_values]
        results = await asyncio.gather(*tasks)
        if any(results):
            processed = True
        if not processed:
            await asyncio.sleep(MODULES_SLEEP_SECONDS)
