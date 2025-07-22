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


def test_f5s5(tmp_path: Path) -> None:
    compose_file, workdir, output_dir = compose_paths(__file__)
    env_file = tmp_path / ".env"
    prepare_dirs(workdir, output_dir)
    write_env(env_file, {"TOKENS_PER_CHUNK": "20", "CHUNK_OVERLAP": "0"})

    doc_path = workdir / "input" / "snippet.txt"
    doc_id = duplicate_finder.compute_hash(doc_path)

    start(compose_file, workdir, env_file)
    try:
        wait_initial(compose_file, workdir, doc_id, env_file)
        results = search_chunks_custom(
            "learning from data",
            filter_expr=f'file_id = "{doc_id}"',
            sort="index:asc",
            limit=3,
            offset=2,
        )
        indexes = [r["index"] for r in results]
        assert indexes == sorted(indexes)
        assert indexes[0] >= 2
    except Exception:
        dump_logs(compose_file, workdir)
        raise
    finally:
        stop(compose_file, workdir, env_file)
