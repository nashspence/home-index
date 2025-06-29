from __future__ import annotations

import json
import logging
import os
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence, Iterator

import features.F5.chunk_utils as chunk_utils
from xmlrpc.server import SimpleXMLRPCServer

from features.F2 import metadata_store

segments_to_chunk_docs = chunk_utils.segments_to_chunk_docs
split_chunk_docs = chunk_utils.split_chunk_docs


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

HOST = os.environ.get("HOST", "0.0.0.0")
PORT = int(os.environ.get("PORT", 9000))
LOGGING_LEVEL = os.environ.get("LOGGING_LEVEL", "INFO")
METADATA_DIRECTORY = metadata_store.metadata_directory()
FILES_DIRECTORY = Path(os.environ.get("FILES_DIRECTORY", "/files"))
BY_ID_DIRECTORY = metadata_store.by_id_directory()
metadata_store.ensure_directories()


def file_path_from_meili_doc(document: Mapping[str, Any]) -> Path:
    relpath = next(iter(document["paths"].keys()))
    return Path(FILES_DIRECTORY / relpath)


def metadata_dir_path_from_doc(name: str, document: Mapping[str, Any]) -> Path:
    dir_path = Path(BY_ID_DIRECTORY / document["id"] / name)
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
    name: str,
    hello_fn: Callable[[], Mapping[str, Any]],
    check_fn: Callable[[Path, Mapping[str, Any], Path], bool],
    run_fn: Callable[[Path, Mapping[str, Any], Path], Any],
    load_fn: Callable[[], Any] | None = None,
    unload_fn: Callable[[], Any] | None = None,
) -> None:
    """Run an XML-RPC server exposing common module hooks."""

    class Handler:
        def hello(self) -> str:
            logging.info("hello")
            return json.dumps(hello_fn())

        def check(self, docs: str) -> str:
            response = set()
            for document in json.loads(docs):
                file_path = file_path_from_meili_doc(document)
                try:
                    metadata_dir_path = metadata_dir_path_from_doc(name, document)
                    with log_to_file_and_stdout(metadata_dir_path / "log.txt"):
                        if check_fn(file_path, document, metadata_dir_path):
                            response.add(document["id"])
                except Exception:
                    logging.exception(f'failed to check "{file_path}"')
            return json.dumps(list(response))

        def load(self) -> None:
            logging.info("load")
            if load_fn:
                load_fn()

        def run(self, document_json: str) -> str:
            document = json.loads(document_json)
            file_path = file_path_from_meili_doc(document)
            metadata_dir_path = metadata_dir_path_from_doc(name, document)
            with log_to_file_and_stdout(metadata_dir_path / "log.txt"):
                result = run_fn(file_path, document, metadata_dir_path)
            return json.dumps(result)

        def unload(self) -> None:
            logging.info("unload")
            if unload_fn:
                unload_fn()

    server = SimpleXMLRPCServer((HOST, PORT), allow_none=True)
    server.register_instance(Handler())
    print(f"Server running at {server.server_address}")
    server.serve_forever()
