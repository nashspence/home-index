from __future__ import annotations

import json
import shutil
import subprocess
import sys
import time
import urllib.request
from pathlib import Path
from typing import Any, Callable

from features.F2 import duplicate_finder

import pytest


def _dump_logs(compose_file: Path, workdir: Path, output_dir: Path) -> None:
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
    timeout: int = 120,
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
    doc_relpaths: list[str],
    setup_input: Callable[[Path], None] | None = None,
) -> list[str]:
    if output_dir.exists():
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True)
    (output_dir / "hello_versions.json").write_text('{"hello_versions": []}')

    input_dir = workdir / "input"
    if input_dir.exists():
        shutil.rmtree(input_dir)
    input_dir.mkdir(parents=True)
    if setup_input:
        setup_input(input_dir)

    metadata_dir = output_dir / "metadata"
    by_id = metadata_dir / "by-id"
    by_path = metadata_dir / "by-path"
    by_id.mkdir(parents=True)
    by_path.mkdir(parents=True)

    doc_ids: list[str] = []
    for i, doc_relpath in enumerate(doc_relpaths, start=1):
        doc_path = input_dir / doc_relpath
        if doc_path.exists():
            doc_id = duplicate_finder.compute_hash(doc_path)
        else:
            doc_id = f"hash{i}"
        doc_ids.append(doc_id)
        doc = {
            "id": doc_id,
            "paths": {doc_relpath: 1.0},
            "paths_list": [doc_relpath],
            "mtime": 1.0,
            "size": 1,
            "type": "text/plain",
            "copies": 1,
            "version": 1,
            "next": "",
        }
        doc_dir = by_id / str(doc["id"])
        doc_dir.mkdir()
        (doc_dir / "document.json").write_text(json.dumps(doc))
        link = by_path / Path(doc_relpath)
        link.parent.mkdir(parents=True, exist_ok=True)
        link.symlink_to(Path("../../by-id") / str(doc["id"]), target_is_directory=True)

    subprocess.run(
        ["docker", "compose", "-f", str(compose_file), "up", "-d"],
        check=True,
        cwd=workdir,
    )
    by_id_dir = output_dir / "metadata" / "by-id"
    deadline = time.time() + 120
    while True:
        if by_id_dir.exists() and any(by_id_dir.iterdir()):
            break
        if time.time() > deadline:
            raise AssertionError("Timed out waiting for metadata")
        time.sleep(0.5)

    return doc_ids


def test_offline_archive_workflow(tmp_path: Path) -> None:
    compose_file = Path(__file__).with_name("docker-compose.yml")
    workdir = compose_file.parent
    output_dir = workdir / "output"

    def offline_setup(input_dir: Path) -> None:
        (input_dir / "archive").mkdir()

    def removed_setup(input_dir: Path) -> None:
        drive = input_dir / "archive" / "drive2"
        drive.mkdir(parents=True)
        (drive / "bar.txt").write_text("persist")

    try:
        ids = _run_once(
            compose_file,
            workdir,
            output_dir,
            ["archive/drive1/foo.txt"],
            offline_setup,
        )
        offline_id = ids[0]
        doc_dir = output_dir / "metadata" / "by-id" / offline_id
        assert (doc_dir / "document.json").exists()
        assert (
            output_dir / "metadata" / "by-path" / "archive" / "drive1" / "foo.txt"
        ).is_symlink()
        docs = _search_meili(f'id = "{offline_id}"', compose_file, workdir, output_dir)
        assert any(doc["id"] == offline_id for doc in docs)

        ids = _run_once(
            compose_file,
            workdir,
            output_dir,
            ["archive/drive2/bar.txt"],
            removed_setup,
        )
        online_id = ids[0]

        docs = _search_meili(f'id = "{online_id}"', compose_file, workdir, output_dir)
        assert any(doc["id"] == online_id for doc in docs)

        doc_dir = output_dir / "metadata" / "by-id" / offline_id
        assert not doc_dir.exists()
        assert not (
            output_dir / "metadata" / "by-path" / "archive" / "drive2" / "foo.txt"
        ).exists()
        assert (
            output_dir / "metadata" / "by-id" / online_id / "document.json"
        ).exists()
        assert (
            output_dir / "metadata" / "by-path" / "archive" / "drive2" / "bar.txt"
        ).is_symlink()
        with pytest.raises(AssertionError):
            _search_meili(f'id = "{offline_id}"', compose_file, workdir, output_dir)
    except Exception:
        _dump_logs(compose_file, workdir, output_dir)
        raise
    finally:
        subprocess.run(
            ["docker", "compose", "-f", str(compose_file), "stop"],
            check=False,
            cwd=workdir,
        )
        subprocess.run(
            ["docker", "compose", "-f", str(compose_file), "rm", "-fsv"],
            check=False,
            cwd=workdir,
        )
