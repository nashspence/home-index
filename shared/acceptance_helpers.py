"""
AsyncDockerLogWatcher  –  tiny, dependency-free (besides docker-py) helper
=========================================================================

• Remembers every log line (FIFO cap optional).
• `await wait_for_sequence(...)` – ordered line/regex/callable matching.
• `await wait_until_quiet(...)`  – no new logs for N seconds.
• `await wait_for_ready(...)`    – HEALTHCHECK or custom predicate.
• `await wait_for_container_stopped(...)` – exit/death detection.
• `assert_no_line(...)`, `dump_logs(...)` for debugging / CI output.

Assumes **plain text logs** (no JSON decoding).
Python ≥ 3.8, Docker SDK ≥ 5.x.

---------------------------------------------------------------------------
"""

from __future__ import annotations

import asyncio
import os
import subprocess
from pathlib import Path
import re
import shutil
import tempfile
import threading
import time
import types
import xxhash
from dataclasses import dataclass
from typing import (
    Any,
    Dict,
    Iterable,
    Callable,
    List,
    Optional,
    Pattern,
    Sequence,
    Mapping,
    Union,
    cast,
    AsyncIterator,
    Awaitable,
)
from contextlib import asynccontextmanager

import docker
from docker.models.containers import Container

# ----- configuration -------------------------------------------------------

VERBOSE = (
    os.environ.get("ACCEPTANCE_VERBOSE")
    or ("true" if os.environ.get("CI") == "true" else "false")
).lower() == "true"
STREAM_LOGS = (os.environ.get("ACCEPTANCE_STREAM_LOGS") or "false").lower() == "true"

# ----- internal logging helpers -------------------------------------------


def _verbose(msg: str) -> None:
    if VERBOSE:
        print(msg, flush=True)


# ----- Helpers -------------------------------------------------------------

LineMatcher = Union[str, Pattern[str], Callable[[str], bool]]


@dataclass
class EventMatcher:
    line: LineMatcher
    within: Optional[float] = None  # seconds allowed since previous match


@dataclass
class LogEvent:
    ts: float
    raw: str
    stream: str  # "stdout" | "stderr"


# ----- Main watcher --------------------------------------------------------


class AsyncDockerLogWatcher:
    """Stream and buffer logs from a Docker container."""

    def __init__(
        self,
        client: docker.DockerClient,
        container_name: str,
        remember_limit: Optional[int] = None,
        poll_interval: float = 0.03,
        start_from_now: bool = True,
        queue_maxsize: int = 10_000,
    ):
        """Create a watcher for ``container_name`` using ``client``.

        Container lookup is deferred until :py:meth:`start` so the watcher can
        be created before the container exists.
        """
        self.client = client
        self.container_name = container_name
        self._container: Optional[Container] = None
        self.remember_limit = remember_limit
        self.poll_interval = poll_interval
        self._start_from_now = start_from_now

        self._q: asyncio.Queue[LogEvent] = (
            asyncio.Queue(maxsize=queue_maxsize) if queue_maxsize else asyncio.Queue()
        )
        self._remembered: List[LogEvent] = []
        self._lock = threading.Lock()

        self._reader_thread: Optional[threading.Thread] = None
        self._stop_evt = threading.Event()
        self._close_stream: Callable[[], None] = lambda: None

    def _set_close_stream(self, closer: Callable[[], None]) -> None:
        with self._lock:
            self._close_stream = closer

    def _started(self) -> bool:
        return self._reader_thread is not None

    @property
    def container(self) -> Container:
        if self._container is None:
            raise RuntimeError("Watcher not started yet")
        return self._container

    # -- public -------------------------------------------------------------

    async def start(self) -> None:
        """Begin streaming logs once the container appears.

        The Docker SDK is synchronous, so ``client.containers.get`` is called in
        a thread and retried until it succeeds or a 60s timeout elapses. This
        matches the polling approach recommended by the docker‑py documentation.
        """
        if self._reader_thread:
            _verbose(f"watcher {self.container_name}: already started")
            return
        self._stop_evt.clear()
        while not self._q.empty():
            try:
                _ = self._q.get_nowait()
            except Exception:
                break
        _verbose(f"watcher {self.container_name}: starting")
        deadline = time.monotonic() + 60
        while True:
            try:
                self._container = await asyncio.to_thread(
                    self.client.containers.get, self.container_name
                )
                break
            except docker.errors.NotFound:
                if time.monotonic() > deadline:
                    raise RuntimeError(
                        f"Container {self.container_name!r} not found within 60s"
                    )
                await asyncio.sleep(self.poll_interval)
        loop = asyncio.get_running_loop()
        self._reader_thread = threading.Thread(
            target=_reader_worker,
            args=(
                self._container,
                self._start_from_now,
                self._stop_evt,
                loop,
                self._ingest_from_thread,
                self._set_close_stream,
            ),
            daemon=True,
        )
        self._reader_thread.start()
        _verbose(f"watcher {self.container_name}: started")

    async def stop(self) -> None:
        """Stop streaming and wait for the reader thread to exit."""
        if not self._reader_thread:
            _verbose(f"watcher {self.container_name}: not started")
            return
        _verbose(f"watcher {self.container_name}: stopping")
        # first, close the blocking Docker-attach stream so the thread wakes up
        try:
            stream = getattr(self._reader_thread, "stream", None)
            if stream:
                stream.close()
        except Exception:
            pass
        self._stop_evt.set()
        try:
            self._close_stream()
        except Exception:
            pass
        thr = self._reader_thread

        def _join() -> None:
            thr.join(timeout=5.0)

        await asyncio.to_thread(_join)
        if thr.is_alive():
            print("WARN: log reader thread did not exit within 5s; continuing.")
        self._reader_thread = None
        self._set_close_stream(lambda: None)
        _verbose(f"watcher {self.container_name}: stopped")

    async def __aenter__(self) -> "AsyncDockerLogWatcher":
        await self.start()
        return self

    async def __aexit__(
        self,
        exc_type: Optional[type[BaseException]],
        exc: Optional[BaseException],
        tb: Optional[types.TracebackType],
    ) -> None:
        await self.stop()

    async def wait_for_ready(
        self,
        timeout: float,
        *,
        predicate: Optional[Callable[["AsyncDockerLogWatcher"], bool]] = None,
        check_health: bool = True,
        expected_health: str = "healthy",
    ) -> None:
        """
        Wait until the container’s healthcheck (or a custom predicate) passes,
        or raise TimeoutError.
        """
        _verbose(f"watcher {self.container_name}: wait_for_ready timeout={timeout}")
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if predicate and predicate(self):
                return
            if check_health:
                await asyncio.to_thread(self.container.reload)
                health = (
                    self.container.attrs.get("State", {})
                    .get("Health", {})
                    .get("Status")
                )
                if health == expected_health:
                    return
            await asyncio.sleep(self.poll_interval)
        self.dump_logs("READY TIMEOUT (tail)")
        raise TimeoutError("Container did not become ready in time")

    async def wait_for_container_stopped(self, timeout: float) -> None:
        """
        Wait until the container exits or dies, or raise TimeoutError.
        """
        if not self._started():
            _verbose(f"watcher {self.container_name}: not started")
            return
        _verbose(
            f"watcher {self.container_name}: wait_for_container_stopped timeout={timeout}"
        )
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            try:
                await asyncio.to_thread(self.container.reload)
            except docker.errors.NotFound:
                return
            if self.container.status in ("exited", "dead"):
                return
            await asyncio.sleep(self.poll_interval)
        self.dump_logs("STOP TIMEOUT (tail)")
        raise TimeoutError("Container did not stop in time")

    async def wait_for_sequence(
        self,
        sequence: Sequence[EventMatcher],
        timeout: float,
        include_stderr: bool = True,
    ) -> List[LogEvent]:
        """
        Match a series of lines/regex/callables in order, each possibly within N seconds
        of the previous one.
        """
        _verbose(
            f"watcher {self.container_name}: wait_for_sequence {len(sequence)} events timeout={timeout}"
        )
        seq = list(sequence)
        matched: List[LogEvent] = []
        idx = 0
        last_ts = time.monotonic()
        deadline = time.monotonic() + timeout

        while idx < len(seq) and time.monotonic() < deadline:
            remain = deadline - time.monotonic()
            if remain <= 0:
                break
            try:
                evt = await asyncio.wait_for(self._q.get(), remain)
            except asyncio.TimeoutError:
                break

            if not include_stderr and evt.stream == "stderr":
                continue

            matcher = seq[idx]
            if _match_line(evt.raw, matcher.line):
                if matcher.within is not None and (evt.ts - last_ts) > matcher.within:
                    self.dump_logs("SEQUENCE TIMING FAILURE")
                    raise TimeoutError(f"Matcher {idx} exceeded 'within' window")
                matched.append(evt)
                last_ts = evt.ts
                idx += 1

        if idx < len(seq):
            self.dump_logs("SEQUENCE NOT MATCHED")
            raise TimeoutError(f"Sequence incomplete ({idx}/{len(seq)})")

        _verbose(f"watcher {self.container_name}: sequence matched {len(seq)} events")
        return matched

    async def wait_for_line(
        self,
        matcher: LineMatcher,
        timeout: float,
        include_stderr: bool = True,
    ) -> LogEvent:
        """
        Wait for the first log line matching `matcher` (string/regex/callable).
        """
        _verbose(
            f"watcher {self.container_name}: wait_for_line {matcher} timeout={timeout}"
        )
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            remain = deadline - time.monotonic()
            try:
                evt = await asyncio.wait_for(self._q.get(), remain)
            except asyncio.TimeoutError:
                break
            if not include_stderr and evt.stream == "stderr":
                continue
            if _match_line(evt.raw, matcher):
                _verbose(f"watcher {self.container_name}: matched line '{matcher}'")
                return evt
        self.dump_logs("WAIT FOR LINE TIMEOUT")
        raise TimeoutError("Timed out waiting for line")

    async def wait_until_quiet(self, quiet_for: float, timeout: float) -> None:
        """
        Wait until no new logs arrive for `quiet_for` seconds, or until `timeout`.
        """
        _verbose(
            f"watcher {self.container_name}: wait_until_quiet quiet_for={quiet_for} timeout={timeout}"
        )
        deadline = time.monotonic() + timeout
        last_seen = time.monotonic()
        while time.monotonic() < deadline:
            try:
                evt = await asyncio.wait_for(self._q.get(), self.poll_interval)
                last_seen = evt.ts
            except asyncio.TimeoutError:
                if time.monotonic() - last_seen >= quiet_for:
                    _verbose(f"watcher {self.container_name}: quiet for {quiet_for}s")
                    return
        self.dump_logs("QUIET WAIT TIMEOUT")
        raise TimeoutError("Logs never went quiet")

    # -- diagnostics --------------------------------------------------------

    def dump_logs(self, header: str = "LOG DUMP", limit: int = 200) -> None:
        """Print last `limit` lines to stdout (pytest shows them on failure)."""
        with self._lock:
            lines = self._remembered[-limit:]
        print(f"\n====== {header} ({len(lines)} lines) ======")
        base = time.time() - time.monotonic()
        for e in lines:
            wall = base + e.ts
            print(f"[{wall:.3f} {e.stream}] {e.raw}")
        print(f"====== END {header} ======\n")

    def assert_no_line(self, matcher: LineMatcher) -> None:
        """Assert that no remembered log line matches `matcher`."""
        with self._lock:
            for e in self._remembered:
                if _match_line(e.raw, matcher):
                    self.dump_logs("FORBIDDEN LINE ENCOUNTERED")
                    raise AssertionError(f"Forbidden line found: {e.raw}")

    # -- internal -----------------------------------------------------------

    def _ingest_from_thread(self, evt: LogEvent) -> None:
        """Called from reader thread; must be thread-safe."""
        try:
            self._q.put_nowait(evt)
        except asyncio.QueueFull:
            # drop the oldest if we hit maxsize
            _ = self._q.get_nowait()
            self._q.put_nowait(evt)

        with self._lock:
            self._remembered.append(evt)
            if self.remember_limit and len(self._remembered) > self.remember_limit:
                overflow = len(self._remembered) - self.remember_limit
                del self._remembered[:overflow]
        if STREAM_LOGS:
            print(
                f"({self.container_name}:{evt.stream}) {evt.raw}",
                flush=True,
            )


# ----- thread worker (blocking Docker API) ---------------------------------


def _reader_worker(
    container: Container,
    start_from_now: bool,
    stop_evt: threading.Event,
    loop: asyncio.AbstractEventLoop,
    ingest_cb: Callable[[LogEvent], None],
    set_close_stream: Callable[[Callable[[], None]], None],
) -> None:
    api = container.client.api
    stream = api.attach(
        container.id,
        stream=True,
        logs=not start_from_now,
        stdout=True,
        stderr=True,
        demux=True,
    )

    close_fn = getattr(stream, "close", lambda: None)
    set_close_stream(close_fn)

    # record it so stop() can close it
    thread = threading.current_thread()
    setattr(thread, "stream", stream)

    try:
        for stdout_chunk, stderr_chunk in _iter_with_timeout(stream, stop_evt):
            if stop_evt.is_set():
                break
            now = time.monotonic()
            if stdout_chunk:
                for line in stdout_chunk.splitlines():
                    _schedule_ingest(loop, ingest_cb, line, "stdout", now)
            if stderr_chunk:
                for line in stderr_chunk.splitlines():
                    _schedule_ingest(loop, ingest_cb, line, "stderr", now)
    finally:
        try:
            close_fn()
        except Exception:
            pass
        set_close_stream(lambda: None)


def _schedule_ingest(
    loop: asyncio.AbstractEventLoop,
    cb: Callable[[LogEvent], None],
    raw_bytes: bytes,
    stream_type: str,
    ts: float,
) -> None:
    decoded = raw_bytes.decode(errors="replace").rstrip("\r\n")
    evt = LogEvent(ts, decoded, stream_type)
    loop.call_soon_threadsafe(cb, evt)


def _iter_with_timeout(
    stream: Iterable[Any],
    stop_evt: threading.Event,
    idle_break: float = 1.0,
) -> Iterable[Any]:
    last = time.monotonic()
    it = iter(stream)
    while True:
        if stop_evt.is_set() and time.monotonic() - last >= idle_break:
            return
        try:
            item = next(it)
        except StopIteration:
            return
        except Exception:
            return
        last = time.monotonic()
        yield item


# ----- utilities -----------------------------------------------------------


def _match_line(line: str, matcher: LineMatcher) -> bool:
    if isinstance(matcher, str):
        return matcher in line
    if isinstance(matcher, re.Pattern):
        return bool(matcher.search(line))
    return bool(matcher(line))


def compose_paths_for_test(test_file: str | Path) -> tuple[Path, Path, Path]:
    """Return compose paths for isolated acceptance test workdir.

    Copies the test directory to a temporary location. If a compose file named
    ``<test_file>.yml`` exists, use it; otherwise fall back to
    ``docker-compose.yml`` from the same directory.
    """
    test_path = Path(test_file).resolve()
    src_dir = test_path.parent
    workdir = Path(tempfile.mkdtemp(prefix=src_dir.name + "_"))
    shutil.copytree(src_dir, workdir, dirs_exist_ok=True)

    specific = workdir / test_path.with_suffix(".yml").name
    compose_file = specific if specific.exists() else workdir / "docker-compose.yml"
    output_dir = workdir / "output"
    return compose_file, workdir, output_dir


def kill_compose_project(compose_file: Path) -> None:
    """Kill and remove all containers from the compose project."""
    project = compose_file.parent.name
    label = f"com.docker.compose.project={project}"
    subprocess.run(
        ["docker", "kill", "$(docker ps -q --filter", f"label={label}", ")"],
        shell=True,
        check=False,
    )
    subprocess.run(
        ["docker", "rm", "-f", "$(docker ps -a -q --filter", f"label={label}", ")"],
        shell=True,
        check=False,
    )


async def _bounded(
    coro: Awaitable[Any],
    timeout: float,
    label: str,
    on_timeout: Callable[[], None] | None = None,
) -> Any:
    try:
        return await asyncio.wait_for(coro, timeout)
    except asyncio.TimeoutError:
        print(f"{label} timeout")
        if on_timeout:
            try:
                on_timeout()
            except Exception:
                pass
        raise


@asynccontextmanager
async def compose_up(
    compose_file: Path,
    *,
    watchers: Dict[str, AsyncDockerLogWatcher] | None = None,
    containers: Iterable[str] | None = None,
) -> AsyncIterator[None]:
    """Start selected compose services and optional log watchers."""
    _verbose(
        "compose_up: starting "
        + (", ".join(containers) if containers else "all containers")
    )
    cmd = ["docker-compose", "-f", str(compose_file), "up", "-d"]
    if containers:
        cmd.extend(containers)
    await asyncio.to_thread(subprocess.run, cmd, check=True)
    if watchers is not None:
        to_start = (
            [watchers[name] for name in containers if name in watchers]
            if containers
            else watchers.values()
        )
        await start_all(to_start)
    _verbose("compose_up: containers started")
    try:
        yield
    finally:
        await compose_down(
            compose_file,
            watchers if watchers is not None else None,
            containers=containers,
        )


async def compose_down(
    compose_file: Path,
    watchers: Dict[str, AsyncDockerLogWatcher] | None = None,
    *,
    containers: Iterable[str] | None = None,
    timeout: float = 30,
) -> None:
    """Stop selected compose services and their watchers."""
    _verbose(
        "compose_down: stopping "
        + (", ".join(containers) if containers else "all containers")
    )
    to_stop = None
    if watchers is not None:
        to_stop = (
            [watchers[name] for name in containers if name in watchers]
            if containers
            else watchers.values()
        )
        await _bounded(
            stop_all(to_stop),
            timeout,
            "stop_all",
            lambda: kill_compose_project(compose_file),
        )
    if containers is None:
        cmd = [
            "docker-compose",
            "-f",
            str(compose_file),
            "down",
            "-v",
            "--remove-orphans",
        ]
    else:
        cmd = ["docker-compose", "-f", str(compose_file), "rm", "-fsv", *containers]
    await _bounded(
        asyncio.to_thread(subprocess.run, cmd, check=True),
        timeout,
        "compose down",
        lambda: kill_compose_project(compose_file),
    )
    if to_stop is not None:
        await _bounded(
            all_stopped(to_stop, timeout=timeout),
            timeout,
            "all_stopped",
            lambda: kill_compose_project(compose_file),
        )
    _verbose("compose_down: done")


# ---------- watcher helpers -------------------------


async def start_all(watchers: Iterable[AsyncDockerLogWatcher]) -> None:
    names = [w.container_name for w in watchers]
    _verbose("start_all: " + ", ".join(names))
    results = await asyncio.gather(
        *(w.start() for w in watchers), return_exceptions=True
    )
    errs = [e for e in results if isinstance(e, BaseException)]
    if errs:
        raise RuntimeError(f"start_all failed: {errs}")
    _verbose("start_all: done")


async def stop_all(watchers: Iterable[AsyncDockerLogWatcher]) -> None:
    names = [w.container_name for w in watchers]
    _verbose("stop_all: " + ", ".join(names))
    results = await asyncio.gather(
        *(w.stop() for w in watchers), return_exceptions=True
    )
    errs = [e for e in results if isinstance(e, BaseException)]
    if errs:
        raise RuntimeError(f"stop_all failed: {errs}")
    _verbose("stop_all: done")


async def all_ready(watchers: Iterable[AsyncDockerLogWatcher], timeout: float) -> None:
    names = [w.container_name for w in watchers]
    _verbose("all_ready: " + ", ".join(names))
    results = await asyncio.gather(
        *(w.wait_for_ready(timeout) for w in watchers if w._started()),
        return_exceptions=True,
    )
    errs = [e for e in results if isinstance(e, BaseException)]
    if errs:
        raise RuntimeError(f"all_ready failed: {errs}")
    _verbose("all_ready: done")


async def all_sequences(
    seq_map: Dict[AsyncDockerLogWatcher, Sequence[EventMatcher]],
    timeout: float,
) -> None:
    await asyncio.gather(
        *(w.wait_for_sequence(seq, timeout) for w, seq in seq_map.items())
    )


async def all_quiet(
    watchers: Iterable[AsyncDockerLogWatcher], timeout: float, quiet_for: float
) -> None:
    names = [w.container_name for w in watchers]
    _verbose(f"all_quiet({quiet_for}s): " + ", ".join(names))
    results = await asyncio.gather(
        *(w.wait_until_quiet(quiet_for, timeout) for w in watchers if w._started()),
        return_exceptions=True,
    )
    errs = [e for e in results if isinstance(e, BaseException)]
    if errs:
        raise RuntimeError(f"all_quiet failed: {errs}")
    _verbose("all_quiet: done")


async def all_stopped(
    watchers: Iterable[AsyncDockerLogWatcher], timeout: float
) -> None:
    names = [w.container_name for w in watchers]
    _verbose("all_stopped: " + ", ".join(names))
    results = await asyncio.gather(
        *(w.wait_for_container_stopped(timeout) for w in watchers if w._started()),
        return_exceptions=True,
    )
    errs = [e for e in results if isinstance(e, BaseException)]
    if errs:
        raise RuntimeError(f"all_stopped failed: {errs}")
    _verbose("all_stopped: done")


@asynccontextmanager
async def make_watchers(
    client: docker.DockerClient,
    container_names: Iterable[str],
    *,
    remember_limit: int = 1000,
    request: Any | None = None,
) -> AsyncIterator[Dict[str, AsyncDockerLogWatcher]]:
    """Yield log watchers and ensure cleanup on exit."""

    watchers: Dict[str, AsyncDockerLogWatcher] = {
        name: AsyncDockerLogWatcher(
            client,
            name,
            remember_limit=remember_limit,
        )
        for name in container_names
    }
    _verbose("make_watchers: " + ", ".join(watchers.keys()))
    try:
        yield watchers
    finally:
        await stop_all(watchers.values())
        if request is not None:
            dump_on_failure(request, container_names, watchers)


def assert_file_indexed(workdir: Path, output_dir: Path, rel_path: str) -> str:
    source = workdir / "input" / rel_path
    hasher = xxhash.xxh64()
    with source.open("rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            hasher.update(chunk)
    digest = cast(str, hasher.hexdigest())
    doc_json = output_dir / "metadata" / "by-id" / digest / "document.json"
    assert doc_json.exists()
    link = output_dir / "metadata" / "by-path" / rel_path
    assert link.is_symlink() and link.resolve().name == digest
    return digest


def dump_on_failure(
    request: Any,
    container_names: Iterable[str],
    watchers: Mapping[str, AsyncDockerLogWatcher] | Iterable[AsyncDockerLogWatcher],
    limit: int = 200,
) -> None:
    rep = getattr(request.node, "rep_call", None)
    if rep and rep.failed:
        print("\n=========== LOG DUMP FOR FAILED TEST ===========")
        if isinstance(watchers, Mapping):
            watchers_map = watchers
        else:
            watchers_map = {w.container_name: w for w in watchers}
        for name in container_names:
            watcher = watchers_map.get(name)
            if watcher:
                watcher.dump_logs(f"CONTAINER ⟨{name}⟩ last {limit} lines")
        print("=========== END LOG DUMP =======================\n")
