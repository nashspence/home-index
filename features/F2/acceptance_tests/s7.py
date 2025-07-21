from __future__ import annotations

from pathlib import Path
import pytest

from shared import compose, compose_paths, dump_logs, search_meili

from .helpers import _run_once, _sync


def f2s7(tmp_path: Path) -> None:
    compose_file, workdir, output_dir = compose_paths(__file__)
    try:
        by_id_dir, by_path_dir, _, _, uniq_docs = _run_once(
            compose_file, workdir, output_dir
        )
        uniq_id = uniq_docs[0]["id"]

        (workdir / "input" / "c.txt").unlink()
        _sync(compose_file, workdir, output_dir)

        with pytest.raises(AssertionError):
            search_meili(compose_file, workdir, f'id = "{uniq_id}"', timeout=5)
        assert not (by_path_dir / "c.txt").exists()
        assert uniq_id not in {p.name for p in by_id_dir.iterdir()}
    except Exception:
        dump_logs(compose_file, workdir)
        raise
    finally:
        compose(
            compose_file, workdir, "down", "--volumes", "--rmi", "local", check=False
        )
