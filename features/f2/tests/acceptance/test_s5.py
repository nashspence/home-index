from __future__ import annotations

from pathlib import Path
import shutil

from shared import compose, compose_paths, dump_logs, search_meili

from .helpers import _run_once, _sync


def test_f2s5(tmp_path: Path) -> None:
    compose_file, workdir, output_dir = compose_paths(__file__)
    try:
        by_id_dir, by_path_dir, _, _, uniq_docs = _run_once(
            compose_file, workdir, output_dir
        )

        shutil.copy(workdir / "input" / "c.txt", workdir / "input" / "c2.txt")
        _sync(compose_file, workdir, output_dir)

        docs = search_meili(compose_file, workdir, 'paths_list = "c2.txt"')
        assert docs
        doc = docs[0]
        assert doc["id"] == uniq_docs[0]["id"]
        assert doc["copies"] == 2
        assert {"c.txt", "c2.txt"} <= set(doc["paths"].keys())
        assert len([d for d in by_id_dir.iterdir() if d.is_dir()]) == 2
    except Exception:
        dump_logs(compose_file, workdir)
        raise
    finally:
        compose(
            compose_file, workdir, "down", "--volumes", "--rmi", "local", check=False
        )
