from __future__ import annotations

from pathlib import Path

from shared import compose, compose_paths, dump_logs, search_meili

from .helpers import _run_once, _sync


def test_f2s6(tmp_path: Path) -> None:
    compose_file, workdir, output_dir = compose_paths(__file__)
    try:
        _, by_path_dir, _, dup_docs, _ = _run_once(compose_file, workdir, output_dir)
        dup_id = dup_docs[0]["id"]

        (workdir / "input" / "b.txt").unlink()
        _sync(compose_file, workdir, output_dir)

        docs = search_meili(compose_file, workdir, f'id = "{dup_id}"')
        assert docs[0]["copies"] == 1
        assert not (by_path_dir / "b.txt").exists()
    except Exception:
        dump_logs(compose_file, workdir)
        raise
    finally:
        compose(
            compose_file, workdir, "down", "--volumes", "--rmi", "local", check=False
        )
