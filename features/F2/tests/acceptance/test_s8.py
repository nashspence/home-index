from __future__ import annotations

from pathlib import Path

from shared import compose, compose_paths, dump_logs, search_meili

from .helpers import _run_once, _sync


def f2s8(tmp_path: Path) -> None:
    compose_file, workdir, output_dir = compose_paths(__file__)
    try:
        by_id_dir, by_path_dir, _, dup_docs, _ = _run_once(
            compose_file, workdir, output_dir
        )
        old_id = dup_docs[0]["id"]

        (workdir / "input" / "b.txt").write_text("changed")
        _sync(compose_file, workdir, output_dir)

        docs = search_meili(compose_file, workdir, 'paths_list = "b.txt"')
        new_id = docs[0]["id"]
        assert new_id != old_id
        assert (by_id_dir / new_id).exists()
        assert (by_id_dir / old_id).exists()
        assert (by_path_dir / "b.txt").resolve().name == new_id
    except Exception:
        dump_logs(compose_file, workdir)
        raise
    finally:
        compose(
            compose_file, workdir, "down", "--volumes", "--rmi", "local", check=False
        )
