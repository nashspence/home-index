from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path
from typing import Any, Callable
import asyncio
import pickle
import struct

# --- acceptance-test handshake ----------------------------------------------
import logging
from logging.handlers import SocketHandler
import socket
from shared.logging_config import files_logger

ACCEPTANCE_LEVEL = logging.INFO + 5
logging.addLevelName(ACCEPTANCE_LEVEL, "ACCEPTANCE")
logging.Logger.acceptance = lambda self, m, *a, **k: self._log(  # type: ignore[attr-defined]
    ACCEPTANCE_LEVEL, m, a, **k
)

_TEST = os.getenv("TEST", "").lower() == "true"
_ACK = b"\x06"
_sock: socket.socket | None = None


class _AcceptServer:
    def __init__(
        self,
        server: asyncio.AbstractServer,
        q: asyncio.Queue[tuple[asyncio.StreamReader, asyncio.StreamWriter]],
    ) -> None:
        self._server = server
        self._q = q

    async def accept(self) -> tuple[asyncio.StreamReader, asyncio.StreamWriter]:
        return await self._q.get()

    def close(self) -> None:
        self._server.close()

    async def wait_closed(self) -> None:
        await self._server.wait_closed()


async def _start_server() -> tuple[_AcceptServer, str, int]:
    """Return a TCP server and its address for log collection."""
    q: asyncio.Queue[tuple[asyncio.StreamReader, asyncio.StreamWriter]] = (
        asyncio.Queue()
    )

    async def handler(r: asyncio.StreamReader, w: asyncio.StreamWriter) -> None:
        q.put_nowait((r, w))

    server = await asyncio.start_server(handler, host="0.0.0.0")
    _, port = server.sockets[0].getsockname()
    return _AcceptServer(server, q), "host.docker.internal", port


async def _next_record(reader: asyncio.StreamReader) -> logging.LogRecord:
    size_bytes = await reader.readexactly(4)
    (size,) = struct.unpack(">I", size_bytes)
    data = await reader.readexactly(size)
    return logging.makeLogRecord(pickle.loads(data))


def _matches(rec: logging.LogRecord, spec: dict[str, Any]) -> bool:
    """Return True if *rec* matches all fields in *spec*."""
    for key, want in spec.items():
        got = getattr(rec, key, None)
        if callable(want):
            if not want(got):
                return False
        elif got != want:
            return False
    return True


async def assert_event_sequence(
    reader: asyncio.StreamReader,
    writer: asyncio.StreamWriter,
    expected: list[dict[str, Any]],
    timeout: float = 5,
) -> None:
    """ACK every log record and assert that *expected* specs appear in order."""
    idx = 0
    while idx < len(expected):
        rec = await asyncio.wait_for(_next_record(reader), timeout)
        writer.write(_ACK)
        await writer.drain()
        if _matches(rec, expected[idx]):
            idx += 1


def _connect_once() -> None:
    """Install SocketHandler and cache the socket for ACK exchange."""
    global _sock
    if _sock or not _TEST:
        return
    host, port = os.getenv("TEST_LOG_TARGET", "127.0.0.1:9020").split(":")
    handler = SocketHandler(host, int(port))
    handler.addFilter(lambda r: r.levelno == ACCEPTANCE_LEVEL)
    root_logger = logging.getLogger()
    if root_logger.level > ACCEPTANCE_LEVEL:
        root_logger.setLevel(ACCEPTANCE_LEVEL)
    root_logger.addHandler(handler)
    handler.createSocket()
    if handler.sock is None:
        raise ConnectionError(f"failed to connect to log server {host}:{port}")
    _sock = handler.sock


def acceptance_step(
    event: str,
    *,
    logger: logging.Logger | None = None,
    **payload: Any,
) -> None:
    """Log *event* at the acceptance level and wait for an ACK when testing."""
    _connect_once()
    (logger or files_logger).log(
        ACCEPTANCE_LEVEL,
        event,
        extra={"event": event, **payload},
    )
    if _TEST:
        assert _sock is not None
        _sock.recv(1)


def dump_logs(compose_file: Path, workdir: Path) -> None:
    """Print logs from all compose containers in service order."""
    for service in ("home-index", "meilisearch", "redis"):
        result = subprocess.run(
            [
                "docker",
                "compose",
                "-f",
                str(compose_file),
                "logs",
                "--no-color",
                service,
            ],
            cwd=workdir,
            check=False,
            capture_output=True,
            text=True,
        )
        if result.returncode == 0:
            if result.stdout:
                print(result.stdout, end="")
            continue
        if "no such service" in result.stderr.lower():
            continue
        if result.stderr:
            print(result.stderr, file=sys.stderr, end="")
    sys.stdout.flush()


def search_meili(
    compose_file: Path,
    workdir: Path,
    filter_expr: str,
    *,
    timeout: int = 120,
    q: str = "",
    index: str = "files",
) -> list[dict[str, Any]]:
    """Return documents matching ``filter_expr`` from Meilisearch."""
    deadline = time.time() + timeout
    url = f"http://localhost:7700/indexes/{index}/search"
    while True:
        try:
            data = {"q": q, "filter": filter_expr}
            req = urllib.request.Request(
                url,
                data=json.dumps(data).encode(),
                headers={"Content-Type": "application/json"},
            )
            with urllib.request.urlopen(req) as resp:
                payload = json.load(resp)
            docs = payload.get("hits") or payload.get("results") or []
            if docs:
                return list(docs)
        except Exception as e:
            print(f"search_meili error: {e}", file=sys.stderr)
        if time.time() > deadline:
            raise AssertionError(
                f"Timed out waiting for search results for: {filter_expr}"
            )
        time.sleep(0.5)


def search_chunks(
    query: str,
    *,
    filter_expr: str = "",
    timeout: int = 300,
) -> list[dict[str, Any]]:
    """Return chunk documents matching ``query`` from Meilisearch."""
    deadline = time.time() + timeout
    url = "http://localhost:7700/indexes/file_chunks/search"
    while True:
        try:
            data = {
                "q": f"query: {query}",
                "hybrid": {"semanticRatio": 1, "embedder": "e5-small"},
            }
            if filter_expr:
                data["filter"] = filter_expr
            req = urllib.request.Request(
                url,
                data=json.dumps(data).encode(),
                headers={"Content-Type": "application/json"},
            )
            with urllib.request.urlopen(req) as resp:
                payload = json.load(resp)
            docs = payload.get("hits") or payload.get("results") or []
            if docs:
                return list(docs)
        except Exception as e:
            print(f"search_chunks error: {e}", file=sys.stderr)
        if time.time() > deadline:
            raise AssertionError("Timed out waiting for search results")
        time.sleep(0.5)


def compose_paths(test_file: str | Path) -> tuple[Path, Path, Path]:
    """Return common compose paths for acceptance tests.

    Parameters
    ----------
    test_file:
        Path to the acceptance test file using the compose setup.
    """
    src = Path(test_file).resolve().parent
    workdir = Path(tempfile.mkdtemp(prefix=src.name + "_"))
    shutil.copytree(src, workdir, dirs_exist_ok=True)
    compose_file = workdir / "docker-compose.yml"
    output_dir = workdir / "output"
    return compose_file, workdir, output_dir


def compose(
    compose_file: Path,
    workdir: Path,
    *args: str,
    env_file: Path | None = None,
    check: bool = True,
) -> subprocess.CompletedProcess[bytes]:
    """Run ``docker compose`` with the given arguments."""
    cmd = ["docker", "compose"]
    env = None
    if env_file:
        cmd += ["--env-file", str(env_file)]
        env = os.environ.copy()
        for line in Path(env_file).read_text().splitlines():
            if not line or line.startswith("#"):
                continue
            key, _, val = line.partition("=")
            env[key] = val
    cmd += ["-f", str(compose_file), *args]
    return subprocess.run(cmd, check=check, cwd=workdir, env=env, capture_output=True)


def wait_for(
    predicate: Callable[[], bool],
    *,
    timeout: int = 120,
    interval: float = 0.5,
    message: str = "condition",
) -> None:
    """Wait until ``predicate`` is true or raise ``AssertionError``."""
    deadline = time.time() + timeout
    while True:
        if predicate():
            return
        if time.time() > deadline:
            raise AssertionError(f"Timed out waiting for {message}")
        time.sleep(interval)
