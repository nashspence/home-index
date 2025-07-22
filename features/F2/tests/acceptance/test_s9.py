from __future__ import annotations

from pathlib import Path
import os

from shared import compose, compose_paths, dump_logs

from .helpers import _run_once, _sync


def f2s9(tmp_path: Path) -> None:
    compose_file, workdir, output_dir = compose_paths(__file__)
    try:
        by_id_dir, by_path_dir, _, _, _ = _run_once(compose_file, workdir, output_dir)

        links = [by_path_dir / name for name in ["a.txt", "b.txt", "c.txt"]]
        targets = [link.resolve() for link in links]
        assert all(by_id_dir in t.parents for t in targets)
        assert all(not Path(os.readlink(link)).is_absolute() for link in links)

        compose(
            compose_file, workdir, "down", "--volumes", "--rmi", "local", check=False
        )
        _sync(compose_file, workdir, output_dir)

        for link, target in zip(links, targets, strict=True):
            assert link.resolve() == target
    except Exception:
        dump_logs(compose_file, workdir)
        raise
    finally:
        compose(
            compose_file, workdir, "down", "--volumes", "--rmi", "local", check=False
        )
