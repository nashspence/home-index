from __future__ import annotations

import json
import os
import shutil
import sys
import time
import urllib.request
from pathlib import Path
from typing import Any


from shared import compose, search_meili, wait_for


def write_env(env_file: Path, extra: dict[str, str] | None = None) -> None:
    entries = [
        f"COMMIT_SHA={os.environ.get('COMMIT_SHA', 'main')}",
        f"MODULE_BASE_IMAGE={os.environ.get('MODULE_BASE_IMAGE', 'home-index-module:ci')}",
    ]
    if extra:
        entries.extend(f"{k}={v}" for k, v in extra.items())
    env_file.write_text("\n".join(entries) + "\n")


def start(compose_file: Path, workdir: Path, env_file: Path) -> None:
    compose(compose_file, workdir, "up", "-d", env_file=env_file)


def stop(compose_file: Path, workdir: Path, env_file: Path) -> None:
    compose(
        compose_file,
        workdir,
        "down",
        "--volumes",
        "--rmi",
        "local",
        env_file=env_file,
        check=False,
    )


def prepare_dirs(workdir: Path, output_dir: Path) -> None:
    if output_dir.exists():
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "modules_config.json").write_text(
        '{"modules": [{"name": "text-module"}]}'
    )


# extended search helper -------------------------------------------------


def search_chunks_custom(
    query: str,
    *,
    filter_expr: str = "",
    sort: str | None = None,
    limit: int | None = None,
    offset: int | None = None,
    timeout: int = 300,
) -> list[dict[str, Any]]:
    deadline = time.time() + timeout
    base_url = os.environ.get("MEILISEARCH_HOST", "http://localhost:7700").rstrip("/")
    url = f"{base_url}/indexes/file_chunks/search"
    while True:
        try:
            data: dict[str, Any] = {
                "q": f"query: {query}",
                "hybrid": {"semanticRatio": 1, "embedder": "e5-small"},
            }
            if filter_expr:
                data["filter"] = filter_expr
            if sort:
                data["sort"] = [sort]
            if limit is not None:
                data["limit"] = limit
            if offset is not None:
                data["offset"] = offset
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
            body = e.read().decode("utf-8", "ignore") if hasattr(e, "read") else ""
            print(
                f"search_chunks_custom HTTPError {e.code} {e.reason}: {body}",
                file=sys.stderr,
            )
        except Exception as e:
            print(f"search_chunks_custom error: {e!r}", file=sys.stderr)
        if time.time() > deadline:
            raise AssertionError("Timed out waiting for search results")
        time.sleep(0.5)


# scenario helpers -------------------------------------------------------


def wait_initial(
    compose_file: Path, workdir: Path, doc_id: str, env_file: Path
) -> Path:
    module = "text-module"
    chunk_file = (
        workdir / "output" / "metadata" / "by-id" / doc_id / module / "chunks.json"
    )
    content_file = chunk_file.with_name("content.json")
    wait_for(chunk_file.exists, timeout=300, message="chunks")
    wait_for(content_file.exists, timeout=300, message="content")
    wait_for(
        lambda: bool(search_meili(compose_file, workdir, f'id = "{doc_id}"')),
        timeout=300,
        message="indexed",
    )
    return chunk_file
