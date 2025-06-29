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


def _dump_logs(compose_file: Path, workdir: Path) -> None:
    """Print logs from all compose containers."""
    subprocess.run(
        ["docker", "compose", "-f", str(compose_file), "logs", "--no-color"],
        cwd=workdir,
        check=False,
    )
    sys.stdout.flush()


def _search_meili(
    filter_expr: str,
    compose_file: Path,
    workdir: Path,
    output_dir: Path,
    timeout: int = 300,
    q: str = "",
) -> list[dict[str, Any]]:
    """Return documents matching ``filter_expr`` from Meilisearch."""
    deadline = time.time() + timeout
    while True:
        try:
            data = json.dumps({"q": q, "filter": filter_expr}).encode()
            req = urllib.request.Request(
                "http://localhost:7700/indexes/files/search",
                data=data,
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
            raise AssertionError(
                f"Timed out waiting for search results for: {filter_expr}"
            )
        time.sleep(0.5)


def _run_once(
    compose_file: Path,
    workdir: Path,
    output_dir: Path,
    env_file: Path,
    home_index_ref: str,
) -> None:
    if output_dir.exists():
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True)
    (output_dir / "hello_versions.json").write_text('{"hello_versions": []}')

    env_file.write_text(f"COMMIT_SHA={home_index_ref}\n")

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
    doc_path = workdir / "input" / "hello.txt"
    doc_id = duplicate_finder.compute_hash(doc_path)
    module_version = (
        output_dir / "metadata" / "by-id" / doc_id / "example_module" / "version.json"
    )
    try:
        deadline = time.time() + 300
        while True:
            time.sleep(0.5)
            if module_version.exists():
                break
            if time.time() > deadline:
                raise AssertionError("Timed out waiting for module output")
        docs = _search_meili(f'id = "{doc_id}"', compose_file, workdir, output_dir)
        assert any(doc["id"] == doc_id for doc in docs)
        data = json.loads(module_version.read_text())
        assert data.get("version") == 1
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
                "down",
                "--volumes",
                "--rmi",
                "local",
            ],
            check=False,
            cwd=workdir,
        )


def test_modules_process_documents(tmp_path: Path) -> None:
    compose_file = Path(__file__).with_name("docker-compose.yml")
    workdir = compose_file.parent
    output_dir = workdir / "output"
    env_file = tmp_path / ".env"
    ref = os.environ.get("COMMIT_SHA", "main")
    _run_once(compose_file, workdir, output_dir, env_file, ref)
