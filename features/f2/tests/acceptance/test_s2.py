from __future__ import annotations

from pathlib import Path

from shared import compose, compose_paths, dump_logs

from .helpers import _run_once


def test_f2s2(tmp_path: Path) -> None:
    compose_file, workdir, output_dir = compose_paths(__file__)
    try:
        _, _, info, dup_docs, uniq_docs = _run_once(compose_file, workdir, output_dir)

        uniq = uniq_docs[0]
        size, mtime, file_hash = info["c.txt"]
        assert uniq["id"] == file_hash
        assert uniq["paths"] == {"c.txt": mtime}
        assert uniq["paths_list"] == ["c.txt"]
        assert uniq["size"] == size
        assert uniq["copies"] == 1
        assert uniq["type"] == "text/plain"
        assert isinstance(uniq["mtime"], float)

        dup = dup_docs[0]
        size_a, mtime_a, hash_a = info["a.txt"]
        size_b, mtime_b, _ = info["b.txt"]
        assert dup["id"] == hash_a
        assert dup["size"] == size_a
        assert dup["paths"] == {"a.txt": mtime_a, "b.txt": mtime_b}
        assert sorted(dup["paths_list"]) == ["a.txt", "b.txt"]
        assert dup["copies"] == 2
        assert dup["type"] == "text/plain"
        assert isinstance(dup["mtime"], float)
    except Exception:
        dump_logs(compose_file, workdir)
        raise
    finally:
        compose(
            compose_file, workdir, "down", "--volumes", "--rmi", "local", check=False
        )
