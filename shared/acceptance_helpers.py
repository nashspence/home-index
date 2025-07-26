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
import subprocess
from pathlib import Path
import re
import shutil
import tempfile
import threading
import time
import types
from datetime import datetime, timezone
import calendar
import xxhash
from dataclasses import dataclass
from typing import (
    Deque,
    Any,
    Dict,
    Iterable,
    Callable,
    List,
    Optional,
    Pattern,
    Sequence,
    Union,
    cast,
    AsyncIterator,
)
from collections import deque
from contextlib import asynccontextmanager

import docker
from docker.models.containers import Container

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
    """
    Stream and buffer logs from a Docker container in an asyncio-friendly way.
    """

    def __init__(
        self,
        container: Container,
        remember_limit: Optional[int] = None,
        poll_interval: float = 0.03,
        start_from_now: bool = True,
        queue_maxsize: Optional[int] = None,
    ):
        """
        :param container: The Docker SDK Container to watch.
        :param remember_limit: Max # of past LogEvents to keep in memory.
        :param poll_interval: How often to poll for readiness/stopped checks.
        :param start_from_now: If True, ignore prior logs and start at current time.
        :param queue_maxsize: If set, bounds the internal asyncio.Queue size.
        """
        self.container = container
        self.remember_limit = remember_limit
        self.poll_interval = poll_interval
        self._start_from_now = start_from_now

        self._q: asyncio.Queue[LogEvent] = (
            asyncio.Queue(maxsize=queue_maxsize) if queue_maxsize else asyncio.Queue()
        )
        self._remembered: List[LogEvent] = []
        self._lock = threading.Lock()

        self._reader_thread: Optional[threading.Thread] = None
        # bounded join to ensure we never hang shutdown even if the thread misbehaves
        self._join_timeout: float = 5.0
        self._stop_evt = threading.Event()

    # -- public -------------------------------------------------------------

    async def start(self) -> None:
        """Begin streaming logs; idempotent."""
        if self._reader_thread:
            return
        loop = asyncio.get_running_loop()
        self._reader_thread = threading.Thread(
            target=_reader_worker,
            args=(
                self.container,
                self._start_from_now,
                self._stop_evt,
                loop,
                self._ingest_from_thread,
            ),
            daemon=True,
        )
        self._reader_thread.start()

    async def stop(self) -> None:
        """Stop streaming and wait for the reader thread to exit."""
        if not self._reader_thread:
            return
        self._stop_evt.set()
        # Join with a timeout so CI can always progress.
        await asyncio.to_thread(self._reader_thread.join, self._join_timeout)
        if self._reader_thread.is_alive():
            # Best-effort notice; tests will also dump logs on failure.
            try:
                short = getattr(self.container, "short_id", "?")
            except Exception:
                short = "?"
            print(
                f"AsyncDockerLogWatcher: reader thread for {short} did not exit within "
                f"{self._join_timeout:.1f}s; continuing."
            )
        # Drop the handle either way.
        self._reader_thread = None

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
                return evt
        self.dump_logs("WAIT FOR LINE TIMEOUT")
        raise TimeoutError("Timed out waiting for line")

    async def wait_until_quiet(self, quiet_for: float, timeout: float) -> None:
        """
        Wait until no new logs arrive for `quiet_for` seconds, or until `timeout`.
        """
        deadline = time.monotonic() + timeout
        last_seen = time.monotonic()
        while time.monotonic() < deadline:
            try:
                evt = await asyncio.wait_for(self._q.get(), self.poll_interval)
                last_seen = evt.ts
            except asyncio.TimeoutError:
                if time.monotonic() - last_seen >= quiet_for:
                    return
        self.dump_logs("QUIET WAIT TIMEOUT")
        raise TimeoutError("Logs never went quiet")

    # -- diagnostics --------------------------------------------------------

    def dump_logs(self, header: str = "LOG DUMP", limit: int = 200) -> None:
        """Print last `limit` lines to stdout (pytest shows them on failure)."""
        with self._lock:
            lines = self._remembered[-limit:]
        print(f"\n====== {header} ({len(lines)} lines) ======")
        for e in lines:
            print(f"[{e.ts:.3f} {e.stream}] {e.raw}")
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


# ----- thread worker (blocking Docker API) ---------------------------------


def _reader_worker(
    container: Container,
    start_from_now: bool,
    stop_evt: threading.Event,
    loop: asyncio.AbstractEventLoop,
    ingest_cb: Callable[[LogEvent], None],
) -> None:
    """
    Poll logs using non-blocking API calls. We keep a `since` watermark per
    stream and de-duplicate locally because the Engine may return lines whose
    timestamp is equal to `since` (comparison is >=).
    """
    api = container.client.api
    since_stdout_dt: Optional[datetime] = None
    since_stderr_dt: Optional[datetime] = None

    if start_from_now:
        now_dt = datetime.now(timezone.utc).replace(tzinfo=None)
        since_stdout_dt = now_dt
        since_stderr_dt = now_dt

    # Dedup: recent keys (stream, ts_prefix, text). Keep small to bound memory.
    seen_keys: Deque[tuple[str, str, str]] = deque(maxlen=2048)
    seen_set: set[tuple[str, str, str]] = set()

    def _push_key(key: tuple[str, str, str]) -> None:
        seen_keys.append(key)
        seen_set.add(key)
        if len(seen_keys) == seen_keys.maxlen:
            oldest = seen_keys[0]
            try:
                seen_set.remove(oldest)
            except KeyError:
                pass

    try:
        while not stop_evt.is_set():
            now = time.time()
            new_any = False

            # stdout
            try:
                out_kwargs = dict(stdout=True, stderr=False, timestamps=True)
                if since_stdout_dt is not None:
                    out_kwargs["since"] = cast(
                        Any, calendar.timegm(since_stdout_dt.timetuple())
                    )
                out_bytes = api.logs(container.id, **out_kwargs)
            except docker.errors.NotFound:
                break
            last_stdout_dt = since_stdout_dt
            for raw_line in out_bytes.splitlines():
                ts_prefix, dt_utc, text = _split_ts_and_text(raw_line)
                if dt_utc is not None:
                    last_stdout_dt = (
                        dt_utc
                        if last_stdout_dt is None or dt_utc > last_stdout_dt
                        else last_stdout_dt
                    )
                key = ("stdout", ts_prefix or "", text)
                if key in seen_set:
                    continue
                _push_key(key)
                if text:
                    new_any = True
                    _schedule_ingest(
                        loop, ingest_cb, text.encode("utf-8", "replace"), "stdout", now
                    )
            since_stdout_dt = last_stdout_dt

            # stderr
            try:
                err_kwargs = dict(stdout=False, stderr=True, timestamps=True)
                if since_stderr_dt is not None:
                    err_kwargs["since"] = cast(
                        Any, calendar.timegm(since_stderr_dt.timetuple())
                    )
                err_bytes = api.logs(container.id, **err_kwargs)
            except docker.errors.NotFound:
                break
            last_stderr_dt = since_stderr_dt
            for raw_line in err_bytes.splitlines():
                ts_prefix, dt_utc, text = _split_ts_and_text(raw_line)
                if dt_utc is not None:
                    last_stderr_dt = (
                        dt_utc
                        if last_stderr_dt is None or dt_utc > last_stderr_dt
                        else last_stderr_dt
                    )
                key = ("stderr", ts_prefix or "", text)
                if key in seen_set:
                    continue
                _push_key(key)
                if text:
                    new_any = True
                    _schedule_ingest(
                        loop, ingest_cb, text.encode("utf-8", "replace"), "stderr", now
                    )
            since_stderr_dt = last_stderr_dt

            try:
                container.reload()
                status = container.status
            except docker.errors.NotFound:
                break

            if status in ("exited", "dead") and not new_any:
                if stop_evt.wait(timeout=0.05):
                    break
                continue

            if stop_evt.wait(timeout=0.05):
                break
    except Exception as e:
        short = getattr(container, "short_id", "?")
        print(f"AsyncDockerLogWatcher reader error for {short}: {e!r}")
        return


_TS_RE = re.compile(
    r"^(?P<prefix>\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?Z)\s+(?P<text>.*)$"
)


def _split_ts_and_text(
    raw_bytes: bytes,
) -> tuple[Optional[str], Optional[datetime], str]:
    """Parse timestamps from Docker log lines.

    Given ``b'2025-07-26T08:15:30.123456789Z message'`` returns
    ``("2025-07-26T08:15:30.123456789Z", datetime(..., tzinfo=None), "message")``.
    If parsing fails, returns ``(None, None, decoded_line)``.
    """

    s = raw_bytes.decode(errors="replace").rstrip("\r\n")
    m = _TS_RE.match(s)
    if not m:
        return None, None, s
    prefix = m.group("prefix")
    text = m.group("text")
    base = prefix[:19]
    frac = ""
    if "." in prefix:
        frac = prefix[20:-1]
    try:
        dt = datetime.strptime(base, "%Y-%m-%dT%H:%M:%S")
        if frac:
            usec = int((frac + "000000")[:6])
            dt = dt.replace(microsecond=usec)
        return prefix, dt.replace(tzinfo=None), text
    except Exception:
        return None, None, s


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


async def compose_up(compose_file: Path) -> None:
    await asyncio.to_thread(
        subprocess.run,
        ["docker-compose", "-f", str(compose_file), "up", "-d"],
        check=True,
    )


async def compose_down(compose_file: Path) -> None:
    await asyncio.to_thread(
        subprocess.run,
        ["docker-compose", "-f", str(compose_file), "down", "-v"],
        check=True,
    )


# ---------- watcher helpers -------------------------


def make_watchers(
    client: docker.DockerClient,
    container_names: Iterable[str],
    remember_limit: int = 1_000,
) -> Dict[str, AsyncDockerLogWatcher]:
    """
    Build (but do not .start()) one watcher per container name.
    """
    return {
        name: AsyncDockerLogWatcher(
            client.containers.get(name), remember_limit=remember_limit
        )
        for name in container_names
    }


async def start_all(watchers: Iterable[AsyncDockerLogWatcher]) -> None:
    await asyncio.gather(*(w.start() for w in watchers))


async def stop_all(watchers: Iterable[AsyncDockerLogWatcher]) -> None:
    await asyncio.gather(*(w.stop() for w in watchers))


async def all_ready(watchers: Iterable[AsyncDockerLogWatcher], timeout: float) -> None:
    await asyncio.gather(*(w.wait_for_ready(timeout) for w in watchers))


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
    await asyncio.gather(*(w.wait_until_quiet(quiet_for, timeout) for w in watchers))


async def all_stopped(
    watchers: Iterable[AsyncDockerLogWatcher], timeout: float
) -> None:
    await asyncio.gather(*(w.wait_for_container_stopped(timeout) for w in watchers))


@asynccontextmanager
async def compose_up_with_watchers(
    compose_file: Path,
    client: docker.DockerClient,
    container_names: Iterable[str],
    *,
    remember_limit: int = 1000,
) -> AsyncIterator[Dict[str, AsyncDockerLogWatcher]]:
    await compose_up(compose_file)
    watchers = make_watchers(client, container_names, remember_limit=remember_limit)
    await start_all(watchers.values())
    try:
        yield watchers
    finally:
        await compose_down_and_stop(compose_file, watchers.values())


async def compose_down_and_stop(
    compose_file: Path,
    watchers: Iterable[AsyncDockerLogWatcher],
    *,
    timeout: float = 30,
) -> None:
    await compose_down(compose_file)
    await all_stopped(watchers, timeout=timeout)
    await stop_all(watchers)


@asynccontextmanager
async def meilisearch_running(compose_file: Path) -> AsyncIterator[None]:
    """Bring up just the meilisearch service and tear it down on exit."""
    await asyncio.to_thread(
        subprocess.run,
        ["docker-compose", "-f", str(compose_file), "up", "-d", "meilisearch"],
        check=True,
    )
    try:
        yield
    finally:
        await compose_down(compose_file)


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
    watchers: Iterable[AsyncDockerLogWatcher],
    limit: int = 200,
) -> None:
    rep = getattr(request.node, "rep_call", None)
    if rep and rep.failed:
        print("\n=========== LOG DUMP FOR FAILED TEST ===========")
        for name, watcher in zip(container_names, watchers):
            watcher.dump_logs(f"CONTAINER ⟨{name}⟩ last {limit} lines")
        print("=========== END LOG DUMP =======================\n")
