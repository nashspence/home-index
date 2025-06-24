import json
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Any
import urllib.request

from features.F2 import duplicate_finder


def _stat_info(path: Path) -> tuple[int, float, str]:
    """Return (size, truncated mtime, hash) for ``path``."""
    stat = path.stat()
    return (
        stat.st_size,
        duplicate_finder.truncate_mtime(stat.st_mtime),
        duplicate_finder.compute_hash(path),
    )


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
) -> list[dict[str, Any]]:
    """Return documents matching ``filter_expr`` from Meilisearch."""
    deadline = time.time() + timeout
    while True:
        try:
            data = json.dumps({"q": "", "filter": filter_expr}).encode()
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


def _run_once(compose_file: Path, workdir: Path, output_dir: Path) -> tuple[
    Path,
    Path,
    list[dict[str, Any]],
    list[dict[str, Any]],
    dict[str, tuple[int, float, str]],
]:
    if output_dir.exists():
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True)
    (output_dir / "hello_versions.json").write_text('{"hello_versions": []}')

    input_dir = workdir / "input"
    info = {name: _stat_info(input_dir / name) for name in ["a.txt", "b.txt", "c.txt"]}
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
        deadline = time.time() + 120
        while True:
            time.sleep(0.5)
            if by_id_dir.exists() and any(by_id_dir.iterdir()):
                break
            if time.time() > deadline:
                raise AssertionError("Timed out waiting for metadata")
        by_path_dir = output_dir / "metadata" / "by-path"
        dup_docs = _search_meili("copies = 2", compose_file, workdir, output_dir)
        unique_docs = _search_meili("copies = 1", compose_file, workdir, output_dir)
        assert len(dup_docs) == 1
        assert len(unique_docs) == 1
        return by_id_dir, by_path_dir, dup_docs, unique_docs, info
    except Exception:
        raise


def test_search_unique_files_by_metadata(tmp_path: Path) -> None:
    compose_file = Path(__file__).with_name("docker-compose.yml")
    workdir = compose_file.parent
    output_dir = workdir / "output"
    try:
        (
            by_id_dir,
            by_path_dir,
            dup_docs,
            unique_docs,
            info,
        ) = _run_once(compose_file, workdir, output_dir)

        subdirs = [d for d in by_id_dir.iterdir() if d.is_dir()]
        docs = [json.loads((d / "document.json").read_text()) for d in subdirs]
        docs_by_paths = {
            tuple(sorted(doc["paths"].keys())): doc
            for doc in docs
            if tuple(sorted(doc["paths"].keys())) != ("__init__.py",)
        }
        assert set(docs_by_paths) == {("a.txt", "b.txt"), ("c.txt",)}
        uniq_doc = docs_by_paths[("c.txt",)]
        dup_doc = docs_by_paths[("a.txt", "b.txt")]

        file_id = uniq_doc["id"]
        input_dir = workdir / "input"
        expected_hash = duplicate_finder.compute_hash(input_dir / "c.txt")
        assert file_id == expected_hash
        mtime_val = uniq_doc["mtime"]

        # confirm document.json fields for unique file
        size_c, mtime_c, hash_c = info["c.txt"]
        assert uniq_doc["size"] == size_c
        assert uniq_doc["paths"] == {"c.txt": mtime_c}
        assert uniq_doc["copies"] == 1
        assert uniq_doc["mtime"] == mtime_c
        assert uniq_doc.get("next", "") == ""

        # confirm document.json fields for duplicates
        size_a, mtime_a, hash_a = info["a.txt"]
        size_b, mtime_b, _ = info["b.txt"]
        assert dup_doc["id"] == hash_a
        assert dup_doc["size"] == size_a
        assert dup_doc["paths"] == {"a.txt": mtime_a, "b.txt": mtime_b}
        assert dup_doc["copies"] == 2
        assert dup_doc["mtime"] == max(mtime_a, mtime_b)
        assert dup_doc.get("next", "") == ""

        link_a = by_path_dir / "a.txt"
        link_b = by_path_dir / "b.txt"
        link_c = by_path_dir / "c.txt"
        assert link_a.is_symlink() and link_b.is_symlink() and link_c.is_symlink()
        assert link_a.resolve() == link_b.resolve()
        assert link_c.resolve().name == file_id

        dup_docs_by_paths = {
            tuple(sorted(doc["paths"].keys())): doc for doc in dup_docs
        }
        assert dup_docs_by_paths.get(("a.txt", "b.txt"))
        assert dup_docs_by_paths[("a.txt", "b.txt")]["copies"] == 2

        uniq_docs_by_paths = {
            tuple(sorted(doc["paths"].keys())): doc for doc in unique_docs
        }
        assert uniq_docs_by_paths.get(("c.txt",))
        assert uniq_docs_by_paths[("c.txt",)]["copies"] == 1

        assert any(
            doc["id"] == file_id
            for doc in _search_meili(
                f'id = "{file_id}"', compose_file, workdir, output_dir
            )
        )
        assert any(
            doc["id"] == file_id
            for doc in _search_meili(
                "paths.c.txt EXISTS",
                compose_file,
                workdir,
                output_dir,
            )
        )
        assert any(
            doc["id"] == file_id
            for doc in _search_meili(
                f"mtime = {mtime_val}", compose_file, workdir, output_dir
            )
        )
        assert any(
            doc["id"] == file_id
            for doc in _search_meili(
                'type = "text/plain"', compose_file, workdir, output_dir
            )
        )
        assert any(
            doc["id"] == file_id
            for doc in _search_meili(
                f"size = {size_c}", compose_file, workdir, output_dir
            )
        )
        assert any(
            doc["id"] == file_id
            for doc in _search_meili("copies = 1", compose_file, workdir, output_dir)
        )
        # multi-field query examples per Meilisearch filter expression docs
        assert any(
            doc["id"] == file_id
            for doc in _search_meili(
                f"size = {size_c} AND copies = 1",
                compose_file,
                workdir,
                output_dir,
            )
        )
        assert any(
            doc["id"] == file_id
            for doc in _search_meili(
                'type = "text/plain" AND paths.c.txt EXISTS',
                compose_file,
                workdir,
                output_dir,
            )
        )

        dup_id = dup_doc["id"]
        assert any(
            doc["id"] == dup_id
            for doc in _search_meili(
                f'id = "{dup_id}"', compose_file, workdir, output_dir
            )
        )
        assert any(
            doc["id"] == dup_id
            for doc in _search_meili(
                "paths.a.txt EXISTS", compose_file, workdir, output_dir
            )
        )
        assert any(
            doc["id"] == dup_id
            for doc in _search_meili(
                f"size = {size_a}", compose_file, workdir, output_dir
            )
        )
        assert any(
            doc["id"] == dup_id
            for doc in _search_meili(
                'type = "text/plain" AND copies = 2',
                compose_file,
                workdir,
                output_dir,
            )
        )
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
