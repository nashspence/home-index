from __future__ import annotations

from pathlib import Path

from shared import compose, compose_paths, dump_logs, search_meili

from .helpers import _run_once


def test_f2s4(tmp_path: Path) -> None:
    compose_file, workdir, output_dir = compose_paths(__file__)
    try:
        _, _, info, _, uniq_docs = _run_once(compose_file, workdir, output_dir)
        size = info["c.txt"][0]
        docs = search_meili(
            compose_file, workdir, f'size = {size} AND type = "text/plain"'
        )
        assert any(doc["id"] == uniq_docs[0]["id"] for doc in docs)
    except Exception:
        dump_logs(compose_file, workdir)
        raise
    finally:
        compose(
            compose_file, workdir, "down", "--volumes", "--rmi", "local", check=False
        )
