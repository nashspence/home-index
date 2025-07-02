import json
import shutil
from pathlib import Path
from typing import Any

from shared import compose, dump_logs, search_meili, wait_for

from features.F2 import duplicate_finder
from features.F2.test.migration_helper import simulate_v0_and_rerun


def _stat_info(path: Path) -> tuple[int, float, str]:
    """Return (size, truncated mtime, hash) for ``path``."""
    stat = path.stat()
    return (
        stat.st_size,
        duplicate_finder.truncate_mtime(stat.st_mtime),
        duplicate_finder.compute_hash(path),
    )


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
    (output_dir / "modules_config.json").write_text('{"modules": []}')

    input_dir = workdir / "input"
    info = {name: _stat_info(input_dir / name) for name in ["a.txt", "b.txt", "c.txt"]}
    compose(compose_file, workdir, "up", "-d")
    try:
        by_id_dir = output_dir / "metadata" / "by-id"
        wait_for(
            lambda: by_id_dir.exists() and any(by_id_dir.iterdir()),
            message="metadata",
        )
        by_path_dir = output_dir / "metadata" / "by-path"
        dup_docs = search_meili(compose_file, workdir, "copies = 2")
        unique_docs = search_meili(compose_file, workdir, "copies = 1")
        assert len(dup_docs) == 1
        assert len(unique_docs) == 1
        return by_id_dir, by_path_dir, dup_docs, unique_docs, info
    except Exception:
        raise


def _run_again(compose_file: Path, workdir: Path, output_dir: Path) -> tuple[
    Path,
    Path,
    list[dict[str, Any]],
    list[dict[str, Any]],
]:
    compose(compose_file, workdir, "up", "-d")
    try:
        by_id_dir = output_dir / "metadata" / "by-id"
        wait_for(
            lambda: by_id_dir.exists() and any(by_id_dir.iterdir()),
            message="metadata",
        )
        by_path_dir = output_dir / "metadata" / "by-path"
        dup_docs = search_meili(compose_file, workdir, "copies = 2")
        unique_docs = search_meili(compose_file, workdir, "copies = 1")
        assert len(dup_docs) == 1
        assert len(unique_docs) == 1
        return by_id_dir, by_path_dir, dup_docs, unique_docs
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

        def read_doc(doc_dir: Path) -> dict[str, Any]:
            wait_for(
                lambda: (doc_dir / "document.json").exists(),
                timeout=30,
                message="document.json",
            )
            data = json.loads((doc_dir / "document.json").read_text())
            assert isinstance(data, dict)
            return data

        docs = [read_doc(d) for d in subdirs]
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
        assert uniq_doc["paths_list"] == ["c.txt"]
        assert uniq_doc["copies"] == 1
        assert uniq_doc["mtime"] == mtime_c

        # confirm document.json fields for duplicates
        size_a, mtime_a, hash_a = info["a.txt"]
        size_b, mtime_b, _ = info["b.txt"]
        assert dup_doc["id"] == hash_a
        assert dup_doc["size"] == size_a
        assert dup_doc["paths"] == {"a.txt": mtime_a, "b.txt": mtime_b}
        assert sorted(dup_doc["paths_list"]) == ["a.txt", "b.txt"]
        assert dup_doc["copies"] == 2
        assert dup_doc["mtime"] == max(mtime_a, mtime_b)

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
            for doc in search_meili(compose_file, workdir, f'id = "{file_id}"')
        )
        assert any(
            doc["id"] == file_id
            for doc in search_meili(compose_file, workdir, 'paths_list = "c.txt"')
        )
        assert any(
            doc["id"] == file_id
            for doc in search_meili(compose_file, workdir, "", q="c.txt")
        )
        assert any(
            doc["id"] == file_id
            for doc in search_meili(compose_file, workdir, f"mtime = {mtime_val}")
        )
        assert any(
            doc["id"] == file_id
            for doc in search_meili(compose_file, workdir, 'type = "text/plain"')
        )
        assert any(
            doc["id"] == file_id
            for doc in search_meili(compose_file, workdir, f"size = {size_c}")
        )
        assert any(
            doc["id"] == file_id
            for doc in search_meili(compose_file, workdir, "copies = 1")
        )
        # multi-field query examples per Meilisearch filter expression docs
        assert any(
            doc["id"] == file_id
            for doc in search_meili(
                compose_file,
                workdir,
                f"size = {size_c} AND copies = 1",
            )
        )
        assert any(
            doc["id"] == file_id
            for doc in search_meili(
                compose_file,
                workdir,
                'type = "text/plain" AND paths_list = "c.txt"',
            )
        )

        dup_id = dup_doc["id"]
        assert any(
            doc["id"] == dup_id
            for doc in search_meili(compose_file, workdir, f'id = "{dup_id}"')
        )
        assert any(
            doc["id"] == dup_id
            for doc in search_meili(compose_file, workdir, 'paths_list = "a.txt"')
        )
        assert any(
            doc["id"] == dup_id
            for doc in search_meili(compose_file, workdir, f"size = {size_a}")
        )
        assert any(
            doc["id"] == dup_id
            for doc in search_meili(
                compose_file,
                workdir,
                'type = "text/plain" AND copies = 2',
            )
        )

        (
            by_id_dir,
            by_path_dir,
            dup_docs,
            unique_docs,
        ) = simulate_v0_and_rerun(
            compose_file,
            workdir,
            output_dir,
            _run_again,
        )
    except Exception:
        dump_logs(compose_file, workdir)
        raise
    finally:
        compose(
            compose_file,
            workdir,
            "down",
            "--volumes",
            "--rmi",
            "local",
            check=False,
        )
