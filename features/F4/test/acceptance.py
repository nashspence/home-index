import json
import shutil
import subprocess
import time
from pathlib import Path
from typing import Any, Iterable
import urllib.request


def _fetch_meili_docs() -> list[dict[str, Any]]:
    deadline = time.time() + 30
    while True:
        try:
            with urllib.request.urlopen(
                "http://localhost:7700/indexes/files/documents"
            ) as resp:
                data = json.load(resp)
            docs: Iterable[dict[str, Any]]
            if isinstance(data, list):
                docs = data
            else:
                docs = data.get("results", [])
            if docs:
                return list(docs)
        except Exception:
            pass
        if time.time() > deadline:
            raise AssertionError("Timed out waiting for meilisearch documents")
        time.sleep(0.5)


def _run_once(
    compose_file: Path, workdir: Path, output_dir: Path
) -> tuple[Path, list[dict[str, Any]]]:
    if output_dir.exists():
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True)
    subprocess.run(
        [
            "docker",
            "compose",
            "-f",
            str(compose_file),
            "up",
            "-d",
        ],
        check=True,
        cwd=workdir,
    )
    try:
        by_id_dir = output_dir / "metadata" / "by-id"
        deadline = time.time() + 60
        while True:
            time.sleep(0.5)
            if by_id_dir.exists() and any(by_id_dir.iterdir()):
                break
            if time.time() > deadline:
                raise AssertionError("Timed out waiting for metadata")
        subprocess.run(
            [
                "docker",
                "compose",
                "-f",
                str(compose_file),
                "stop",
            ],
            check=True,
            cwd=workdir,
        )
        docs = _fetch_meili_docs()
        return by_id_dir, docs
    finally:
        subprocess.run(
            [
                "docker",
                "compose",
                "-f",
                str(compose_file),
                "rm",
                "-fsv",
            ],
            check=False,
            cwd=workdir,
        )


def test_duplicates_detected(tmp_path: Path) -> None:
    compose_file = Path(__file__).with_name("docker-compose.yml")
    workdir = compose_file.parent
    output_dir = workdir / "output"
    by_id_dir, meili_docs = _run_once(compose_file, workdir, output_dir)
    subdirs = [d for d in by_id_dir.iterdir() if d.is_dir()]
    assert len(subdirs) == 2
    docs = [json.loads((d / "document.json").read_text()) for d in subdirs]
    docs_by_paths = {tuple(sorted(doc["paths"].keys())): doc for doc in docs}
    assert set(docs_by_paths) == {("a.txt", "b.txt"), ("c.txt",)}
    assert docs_by_paths[("a.txt", "b.txt")]["copies"] == 2
    assert docs_by_paths[("c.txt",)]["copies"] == 1

    docs_by_paths = {tuple(sorted(doc["paths"].keys())): doc for doc in meili_docs}
    assert set(docs_by_paths) == {("a.txt", "b.txt"), ("c.txt",)}
    assert docs_by_paths[("a.txt", "b.txt")]["copies"] == 2
    assert docs_by_paths[("c.txt",)]["copies"] == 1
