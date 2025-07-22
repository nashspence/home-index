from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Callable


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
        except urllib.error.HTTPError as e:
            body = e.read().decode(errors="ignore")
            print(
                f"search_meili(index={index!r}, filter={filter_expr!r}) HTTP {e.code}: {body}",
                file=sys.stderr,
                flush=True,
            )
        except Exception as e:
            print(
                f"search_meili(index={index!r}, filter={filter_expr!r}) error: {type(e).__name__}: {e}",
                file=sys.stderr,
                flush=True,
            )
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
        except urllib.error.HTTPError as e:
            body = e.read().decode(errors="ignore")
            print(
                f"search_chunks(filter={filter_expr!r}, query={query!r}) HTTP {e.code}: {body}",
                file=sys.stderr,
                flush=True,
            )
        except Exception as e:
            print(
                f"search_chunks(filter={filter_expr!r}, query={query!r}) error: {type(e).__name__}: {e}",
                file=sys.stderr,
                flush=True,
            )
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
