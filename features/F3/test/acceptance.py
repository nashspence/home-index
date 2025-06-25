import json
import shutil
import subprocess
import sys
import time
import urllib.request
from pathlib import Path
from typing import Any


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
    setup_input: callable | None = None,
) -> None:
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

    for i, doc_relpath in enumerate(doc_relpaths, start=1):
        doc = {
            "id": f"hash{i}",
            "paths": {doc_relpath: 1.0},
            "paths_list": [doc_relpath],
            "mtime": 1.0,
            "size": 1,
            "type": "text/plain",
            "copies": 1,
            "version": 1,
            "next": "",
        }
        doc_dir = by_id / doc["id"]
        doc_dir.mkdir()
        (doc_dir / "document.json").write_text(json.dumps(doc))
        link = by_path / Path(doc_relpath)
        link.parent.mkdir(parents=True)
        link.symlink_to(Path("../../by-id") / doc["id"], target_is_directory=True)

    subprocess.run(
        ["docker", "compose", "-f", str(compose_file), "up", "-d"],
        check=True,
        cwd=workdir,
    )
    try:
        by_id_dir = output_dir / "metadata" / "by-id"
        deadline = time.time() + 120
        while True:
            if by_id_dir.exists() and any(by_id_dir.iterdir()):
                break
            if time.time() > deadline:
                raise AssertionError("Timed out waiting for metadata")
            time.sleep(0.5)
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
        _run_once(
            compose_file,
            workdir,
            output_dir,
            ["archive/drive1/foo.txt"],
            offline_setup,
        )

        doc_dir = output_dir / "metadata" / "by-id" / "hash1"
        assert (doc_dir / "document.json").exists()
        assert (
            output_dir / "metadata" / "by-path" / "archive" / "drive1" / "foo.txt"
        ).is_symlink()
        docs = _search_meili('id = "hash1"', compose_file, workdir)
        assert any(doc["id"] == "hash1" for doc in docs)

        _run_once(
            compose_file,
            workdir,
            output_dir,
            ["archive/drive2/foo.txt", "archive/drive2/bar.txt"],
            removed_setup,
        )

        doc_dir = output_dir / "metadata" / "by-id" / "hash1"
        assert not doc_dir.exists()
        assert not (
            output_dir / "metadata" / "by-path" / "archive" / "drive2" / "foo.txt"
        ).exists()
        assert (output_dir / "metadata" / "by-id" / "hash2" / "document.json").exists()
        assert (
            output_dir / "metadata" / "by-path" / "archive" / "drive2" / "bar.txt"
        ).is_symlink()
        docs = _search_meili('id = "hash1"', compose_file, workdir)
        assert not docs
        docs = _search_meili('id = "hash2"', compose_file, workdir)
        assert any(doc["id"] == "hash2" for doc in docs)
    except Exception:
        _dump_logs(compose_file, workdir)
        raise
