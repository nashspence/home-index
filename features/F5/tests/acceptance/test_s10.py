from __future__ import annotations

from pathlib import Path

from shared import compose_paths, dump_logs

from .helpers import (
    prepare_dirs,
    start,
    stop,
    write_env,
    wait_initial,
    search_chunks_custom,
)
from features.F2 import duplicate_finder


def test_f5s10(tmp_path: Path) -> None:
    compose_file, workdir, output_dir = compose_paths(__file__)
    env_file = tmp_path / ".env"
    prepare_dirs(workdir, output_dir)
    write_env(env_file)

    doc_path = workdir / "input" / "snippet.txt"
    doc_id = duplicate_finder.compute_hash(doc_path)

    start(compose_file, workdir, env_file)
    try:
        wait_initial(compose_file, workdir, doc_id, env_file)
        results = search_chunks_custom(
            "learning from data",
            filter_expr="module = 'text-module'",
        )
        assert results and all(r["module"] == "text-module" for r in results)
    except Exception:
        dump_logs(compose_file, workdir)
        raise
    finally:
        stop(compose_file, workdir, env_file)
