from __future__ import annotations

from pathlib import Path
import shutil

from shared import compose, compose_paths, dump_logs, search_meili

from .helpers import _run_once, _sync


def test_f2s10(tmp_path: Path) -> None:
    compose_file, workdir, output_dir = compose_paths(__file__)
    try:
        _, _, _, _, uniq_docs = _run_once(compose_file, workdir, output_dir)

        shutil.copy(workdir / "input" / "c.txt", workdir / "input" / "extra.txt")
        _sync(compose_file, workdir, output_dir)

        docs = search_meili(compose_file, workdir, "copies > 1")
        assert any("extra.txt" in doc.get("paths_list", []) for doc in docs)
        assert any(doc["id"] == uniq_docs[0]["id"] for doc in docs)
    except Exception:
        dump_logs(compose_file, workdir)
        raise
    finally:
        compose(
            compose_file, workdir, "down", "--volumes", "--rmi", "local", check=False
        )
