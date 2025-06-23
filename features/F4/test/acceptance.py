import json
import shutil
import subprocess
import time
from pathlib import Path
from typing import cast


def _search_meili(filter_expr: str) -> list[dict[str, object]]:
    from meilisearch_python_sdk import Client

    client = Client("http://localhost:7700")
    res = client.index("files").search("", {"filter": filter_expr})
    return cast(list[dict[str, object]], res["hits"])


def _run_once(
    compose_file: Path, workdir: Path, output_dir: Path
) -> tuple[Path, dict[str, list[dict[str, object]]]]:
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
        docs = {
            "duplicate": _search_meili("copies = 2"),
            "unique": _search_meili("copies = 1"),
        }
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
    by_id_dir, search_results = _run_once(compose_file, workdir, output_dir)
    subdirs = [d for d in by_id_dir.iterdir() if d.is_dir()]
    assert len(subdirs) == 2
    docs = [json.loads((d / "document.json").read_text()) for d in subdirs]
    docs_by_paths = {tuple(sorted(doc["paths"].keys())): doc for doc in docs}
    assert set(docs_by_paths) == {("a.txt", "b.txt"), ("c.txt",)}
    assert docs_by_paths[("a.txt", "b.txt")]["copies"] == 2
    assert docs_by_paths[("c.txt",)]["copies"] == 1

    dup_results = search_results["duplicate"]
    uniq_results = search_results["unique"]
    assert len(dup_results) == 1
    assert len(uniq_results) == 1
    assert dup_results[0]["copies"] == 2
    assert uniq_results[0]["copies"] == 1
    assert dup_results[0]["id"] == docs_by_paths[("a.txt", "b.txt")]["id"]
    assert uniq_results[0]["id"] == docs_by_paths[("c.txt",)]["id"]
