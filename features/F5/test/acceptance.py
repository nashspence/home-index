import json
import shutil
import subprocess
import sys
import time
import urllib.request
from pathlib import Path
from typing import Any
import os

from features.F2 import duplicate_finder
from shared.embedding import embed_texts


def _dump_logs(compose_file: Path, workdir: Path) -> None:
    subprocess.run(
        ["docker", "compose", "-f", str(compose_file), "logs", "--no-color"],
        cwd=workdir,
        check=False,
    )
    sys.stdout.flush()


def _search_chunks(
    vector: list[float],
    compose_file: Path,
    workdir: Path,
    filter_expr: str = "",
    timeout: int = 300,
) -> list[dict[str, Any]]:
    deadline = time.time() + timeout
    while True:
        try:
            data = {"vector": vector}
            if filter_expr:
                data["filter"] = filter_expr
            req = urllib.request.Request(
                "http://localhost:7700/indexes/file_chunks/search",
                data=json.dumps(data).encode(),
                headers={"Content-Type": "application/json"},
            )
            with urllib.request.urlopen(req) as resp:
                payload = json.load(resp)
            docs = payload.get("hits") or payload.get("results") or []
            if docs:
                return list(docs)
        except Exception:
            pass
        if time.time() > deadline:
            raise AssertionError("Timed out waiting for search results")
        time.sleep(0.5)


def _run_once(
    compose_file: Path,
    workdir: Path,
    output_dir: Path,
    env_file: Path,
    ref: str,
) -> tuple[str, str]:
    if output_dir.exists():
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True)
    (output_dir / "hello_versions.json").write_text('{"hello_versions": []}')

    env_file.write_text(f"HOME_INDEX_REF={ref}\n")

    subprocess.run(
        [
            "docker",
            "compose",
            "--env-file",
            str(env_file),
            "-f",
            str(compose_file),
            "up",
            "-d",
        ],
        check=True,
        cwd=workdir,
    )
    doc_path = workdir / "input" / "snippet.txt"
    doc_id = duplicate_finder.compute_hash(doc_path)
    chunk_json = (
        output_dir
        / "metadata"
        / "by-id"
        / doc_id
        / "chunk_module"
        / f"chunk_module_{doc_id}_0.json"
    )
    try:
        deadline = time.time() + 300
        while True:
            time.sleep(0.5)
            if chunk_json.exists():
                break
            if time.time() > deadline:
                raise AssertionError("Timed out waiting for chunk metadata")
        return doc_id, f"chunk_module_{doc_id}_0"
    except Exception:
        _dump_logs(compose_file, workdir)
        raise
    finally:
        subprocess.run(
            [
                "docker",
                "compose",
                "--env-file",
                str(env_file),
                "-f",
                str(compose_file),
                "stop",
            ],
            check=False,
            cwd=workdir,
        )
        subprocess.run(
            [
                "docker",
                "compose",
                "--env-file",
                str(env_file),
                "-f",
                str(compose_file),
                "rm",
                "-fsv",
            ],
            check=False,
            cwd=workdir,
        )


def test_search_file_chunks_by_concept(tmp_path: Path) -> None:
    compose_file = Path(__file__).with_name("docker-compose.yml")
    workdir = compose_file.parent
    output_dir = workdir / "output"
    env_file = tmp_path / ".env"
    ref = os.environ.get("HOME_INDEX_REF", "main")
    file_id, chunk_id = _run_once(compose_file, workdir, output_dir, env_file, ref)
    vector = embed_texts(["concept search works"])[0]
    results = _search_chunks(vector, compose_file, workdir, f'file_id = "{file_id}"')
    assert any(doc["id"] == chunk_id for doc in results)
