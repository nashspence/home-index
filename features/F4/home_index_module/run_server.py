from __future__ import annotations

import json
import logging
import os
import time
import uuid
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Callable, Iterator, Mapping, Sequence, cast
from urllib.parse import urlparse

try:
    import redis
except Exception:  # pragma: no cover - optional for tests
    redis = None

try:
    import yaml
except Exception:  # pragma: no cover - optional for tests
    yaml = None


def metadata_directory() -> Path:
    """Return the root metadata directory."""
    return Path(os.environ.get("METADATA_DIRECTORY", "/files/metadata"))


def by_id_directory() -> Path:
    """Return the directory where metadata is stored by file ID."""
    return Path(os.environ.get("BY_ID_DIRECTORY", str(metadata_directory() / "by-id")))


def ensure_directories() -> None:
    """Create required directories if they do not exist."""
    for path in [metadata_directory(), by_id_directory()]:
        path.mkdir(parents=True, exist_ok=True)


def setup_debugger() -> None:
    """Enable debugpy debugging when DEBUG environment variable is true."""
    if str(os.environ.get("DEBUG", "False")) == "True":
        import debugpy

        debugpy.listen(("0.0.0.0", 5678))
        if str(os.environ.get("WAIT_FOR_DEBUGPY_CLIENT", "False")) == "True":
            print("Waiting for debugger to attach...")
            debugpy.wait_for_client()
            print("Debugger attached.")
            debugpy.breakpoint()


setup_debugger()

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s"
)

LOGGING_LEVEL = os.environ.get("LOGGING_LEVEL", "INFO")
REDIS_HOST = os.environ.get("REDIS_HOST", "redis")
QUEUE_NAME = os.environ.get("QUEUE_NAME", "module")
WORKER_ID = os.environ.get("WORKER_ID", str(uuid.uuid4()))
RESOURCE_SHARES = os.environ.get("RESOURCE_SHARES", "")
TIMEOUT = int(os.environ.get("TIMEOUT", "300"))
DONE_QUEUE = "modules:done"
TIMEOUT_SET = "timeouts"
METADATA_DIRECTORY = metadata_directory()
FILES_DIRECTORY = Path(os.environ.get("FILES_DIRECTORY", "/files"))
BY_ID_DIRECTORY = by_id_directory()
ensure_directories()


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


def parse_resource_shares() -> list[dict[str, Any]]:
    if not RESOURCE_SHARES:
        return []
    if yaml is not None:
        try:
            return cast(list[dict[str, Any]], yaml.safe_load(RESOURCE_SHARES)) or []
        except Exception:
            return []
    groups: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None
    for line in RESOURCE_SHARES.strip().splitlines():
        line = line.strip()
        if line.startswith("-"):
            if current:
                groups.append(current)
            current = {}
            line = line[1:].strip()
            if line:
                key, val = line.split(":", 1)
                current[key.strip()] = (
                    int(val.strip()) if val.strip().isdigit() else val.strip()
                )
        elif ":" in line and current is not None:
            key, val = line.split(":", 1)
            current[key.strip()] = (
                int(val.strip()) if val.strip().isdigit() else val.strip()
            )
    if current:
        groups.append(current)
    return groups


RESOURCE_SHARE_GROUPS = parse_resource_shares()


def file_path_from_meili_doc(document: Mapping[str, Any]) -> Path:
    relpath = next(iter(document["paths"].keys()))
    return Path(FILES_DIRECTORY / relpath)


def metadata_dir_path_from_doc(document: Mapping[str, Any]) -> Path:
    dir_path = Path(BY_ID_DIRECTORY / document["id"] / QUEUE_NAME)
    dir_path.mkdir(parents=True, exist_ok=True)
    return dir_path


def read_json(path: str | Path) -> Any:
    path = Path(path)
    with open(path, "r") as file:
        return json.load(file)


def write_json(path: str | Path, data: Any) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as file:
        json.dump(data, file, indent=4)


def load_version(metadata_dir_path: str | Path) -> Any | None:
    version_path = Path(metadata_dir_path) / "version.json"
    if version_path.exists():
        return read_json(version_path)
    return None


def save_version(metadata_dir_path: str | Path, data: Any) -> None:
    write_json(Path(metadata_dir_path) / "version.json", data)


def save_version_with_exceptions(
    metadata_dir_path: str | Path, version: int, **exceptions: Any
) -> None:
    """Save ``version`` metadata alongside any exception details."""
    data: dict[str, Any] = {"version": version}
    for key, exc in exceptions.items():
        if exc is not None:
            data[key] = str(exc)
            # also store generic 'exception' if not already present
            if "exception" not in data:
                data["exception"] = str(exc)
    save_version(metadata_dir_path, data)


def apply_migrations(
    from_version: int,
    migrations: Sequence[Callable[..., tuple[Any, list[dict[str, Any]]]]],
    *args: Any,
    target_version: int,
) -> tuple[Any | None, list[dict[str, Any]], int]:
    """Run one migration step from ``from_version`` toward ``target_version``."""
    if from_version >= target_version:
        return None, [], from_version

    if from_version >= len(migrations) or migrations[from_version] is None:
        return None, [], from_version

    migration = migrations[from_version]
    segments, docs = migration(*args)
    chunk_docs = docs if docs else []
    return segments, chunk_docs, from_version + 1


def apply_migrations_if_needed(
    metadata_dir_path: str | Path,
    migrations: Sequence[Callable[..., tuple[Any, list[dict[str, Any]]]]],
    *args: Any,
    target_version: int,
) -> tuple[Any | None, list[dict[str, Any]], int]:
    """Load version info and apply pending migrations until up to date."""
    version_info = load_version(metadata_dir_path) or {}
    current = version_info.get("version", 0)
    all_chunk_docs = []
    segments = None
    while current < target_version:
        segs, docs, new_ver = apply_migrations(
            current, migrations, *args, target_version=target_version
        )
        if new_ver == current:
            break
        current = new_ver
        if segs is not None:
            segments = segs
        all_chunk_docs.extend(docs)
    if current != version_info.get("version"):
        save_version(metadata_dir_path, {"version": current})
    return segments, all_chunk_docs, current


@contextmanager
def log_to_file_and_stdout(file_path: str | Path) -> Iterator[None]:
    file_handler = logging.FileHandler(file_path)
    file_handler.setLevel(LOGGING_LEVEL)
    file_formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")
    file_handler.setFormatter(file_formatter)

    stream_handler = logging.StreamHandler()
    stream_handler.setLevel(LOGGING_LEVEL)
    stream_formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")
    stream_handler.setFormatter(stream_formatter)

    root_logger = logging.getLogger()
    root_logger.addHandler(file_handler)
    root_logger.addHandler(stream_handler)

    try:
        yield
    finally:
        root_logger.removeHandler(file_handler)
        file_handler.close()
        root_logger.removeHandler(stream_handler)


def run_server(
    check_fn: Callable[[Path, Mapping[str, Any], Path], bool],
    run_fn: Callable[[Path, Mapping[str, Any], Path], Any],
    load_fn: Callable[[], Any] | None = None,
    unload_fn: Callable[[], Any] | None = None,
) -> None:
    """Process tasks from Redis queues with optional resource sharing."""
    client = make_redis_client()

    for group in RESOURCE_SHARE_GROUPS:
        q = f"{group['name']}:share"
        ttl_set = f"{q}:ttl"
        if WORKER_ID not in client.lrange(q, 0, -1):
            client.rpush(q, WORKER_ID)
        client.zadd(ttl_set, {WORKER_ID: time.time() + TIMEOUT})

    def wait_turn(group: dict[str, Any]) -> None:
        q = f"{group['name']}:share"
        ttl_set = f"{q}:ttl"
        while True:
            members = client.lrange(q, 0, -1)
            if WORKER_ID not in members:
                client.rpush(q, WORKER_ID)
                client.zadd(ttl_set, {WORKER_ID: time.time() + TIMEOUT})
            head = members[0] if members else None
            if head == WORKER_ID:
                client.zadd(ttl_set, {WORKER_ID: time.time() + TIMEOUT})
                return
            if head is not None:
                expire = client.zscore(ttl_set, head)
                if expire is not None and float(expire) < time.time():
                    client.lrem(q, 0, head)
                    client.zrem(ttl_set, head)
                    rotate(group)
            time.sleep(1)

    def rotate(group: dict[str, Any]) -> None:
        q = f"{group['name']}:share"
        ttl_set = f"{q}:ttl"
        head = client.lpop(q)
        if head:
            client.zrem(ttl_set, head)
            client.rpush(q, head)

    def add_timeout(queue: str, doc_json: str) -> str:
        key = json.dumps({"q": queue, "d": doc_json})
        with client.pipeline() as pipe:
            pipe.zadd(TIMEOUT_SET, {key: time.time() + TIMEOUT})
            pipe.rpush(f"{queue}:processing", doc_json)
            pipe.execute()
        return key

    def remove_timeout(queue: str, doc_json: str) -> bool:
        key = json.dumps({"q": queue, "d": doc_json})
        exists = client.zscore(TIMEOUT_SET, key) is not None
        client.zrem(TIMEOUT_SET, key)
        client.lrem(f"{queue}:processing", 0, doc_json)
        return exists

    def process_check() -> bool:
        doc_json = client.lpop(f"{QUEUE_NAME}:check")
        if not doc_json:
            return False
        add_timeout(f"{QUEUE_NAME}:check", doc_json)
        document = json.loads(doc_json)
        file_path = file_path_from_meili_doc(document)
        metadata_dir_path = metadata_dir_path_from_doc(document)
        should_run = check_fn(file_path, document, metadata_dir_path)
        if should_run:
            (metadata_dir_path / "log.txt").touch(exist_ok=True)
        key = json.dumps({"q": f"{QUEUE_NAME}:check", "d": doc_json})
        expiration = client.zscore(TIMEOUT_SET, key)
        if expiration is not None and time.time() > float(expiration):
            return True
        removed = remove_timeout(f"{QUEUE_NAME}:check", doc_json)
        if not removed:
            return True
        if should_run:
            client.rpush(f"{QUEUE_NAME}:run", doc_json)
        else:
            client.rpush(
                DONE_QUEUE, json.dumps({"module": QUEUE_NAME, "document": document})
            )
        for group in RESOURCE_SHARE_GROUPS:
            client.zadd(
                f"{group['name']}:share:ttl", {WORKER_ID: time.time() + TIMEOUT}
            )
        return True

    def process_run() -> bool:
        try:
            doc_json = client.blmove(
                f"{QUEUE_NAME}:run",
                f"{QUEUE_NAME}:run:processing",
                "LEFT",
                "RIGHT",
                timeout=1,
            )
        except Exception:
            item = client.blpop(f"{QUEUE_NAME}:run", timeout=1)
            if not item:
                return False
            doc_json = item[1]
        if not doc_json:
            return False
        key = add_timeout(f"{QUEUE_NAME}:run", doc_json)
        document = json.loads(doc_json)
        file_path = file_path_from_meili_doc(document)
        metadata_dir_path = metadata_dir_path_from_doc(document)
        with log_to_file_and_stdout(metadata_dir_path / "log.txt"):
            result = run_fn(file_path, document, metadata_dir_path)
        expiration = client.zscore(TIMEOUT_SET, key)
        if expiration is not None and time.time() > float(expiration):
            return True
        removed = remove_timeout(f"{QUEUE_NAME}:run", doc_json)
        if not removed:
            return True
        for group in RESOURCE_SHARE_GROUPS:
            client.zadd(
                f"{group['name']}:share:ttl", {WORKER_ID: time.time() + TIMEOUT}
            )
        if isinstance(result, dict) and "document" in result:
            payload = result
        else:
            payload = {"document": result}
        payload["module"] = QUEUE_NAME
        client.rpush(DONE_QUEUE, json.dumps(payload))
        return True

    while True:
        while process_check():
            pass
        groups = RESOURCE_SHARE_GROUPS or [{"name": "", "seconds": 0}]
        for group in groups:
            if group["name"]:
                wait_turn(group)
            if load_fn:
                load_fn()
            start = time.time()
            while True:
                while process_check():
                    pass
                processed = process_run()
                if not processed and not group["name"]:
                    break
                if group["name"] and time.time() - start >= int(group["seconds"]):
                    break
            if unload_fn:
                unload_fn()
            if group["name"]:
                rotate(group)
