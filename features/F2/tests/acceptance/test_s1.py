from __future__ import annotations

from pathlib import Path

from shared import compose, compose_paths, dump_logs

from .helpers import _run_once


def f2s1(tmp_path: Path) -> None:
    compose_file, workdir, output_dir = compose_paths(__file__)
    try:
        by_id_dir, by_path_dir, _, _, uniq_docs = _run_once(
            compose_file, workdir, output_dir
        )

        dirs = [d for d in by_id_dir.iterdir() if d.is_dir()]
        assert len(dirs) == 2

        link_a = by_path_dir / "a.txt"
        link_b = by_path_dir / "b.txt"
        link_c = by_path_dir / "c.txt"
        assert link_a.is_symlink() and link_b.is_symlink() and link_c.is_symlink()
        assert link_a.resolve() == link_b.resolve()
        assert link_c.resolve().name == uniq_docs[0]["id"]
    except Exception:
        dump_logs(compose_file, workdir)
        raise
    finally:
        compose(
            compose_file, workdir, "down", "--volumes", "--rmi", "local", check=False
        )
