from __future__ import annotations

from pathlib import Path

from shared import compose_paths, dump_logs, search_chunks, wait_for

from .helpers import prepare_dirs, start, stop, write_env, wait_initial
from features.f2 import duplicate_finder


def test_f5s2(tmp_path: Path) -> None:
    compose_file, workdir, output_dir = compose_paths(__file__)
    env_file = tmp_path / ".env"
    prepare_dirs(workdir, output_dir)
    write_env(env_file)

    doc_path = workdir / "input" / "snippet.txt"
    doc_id = duplicate_finder.compute_hash(doc_path)

    start(compose_file, workdir, env_file)
    try:
        wait_initial(compose_file, workdir, doc_id, env_file)
        new_file = workdir / "input" / "extra.txt"
        new_file.write_text("extra content for scenario two")
        new_id = duplicate_finder.compute_hash(new_file)
        new_chunk = (
            output_dir / "metadata" / "by-id" / new_id / "text-module" / "chunks.json"
        )
        wait_for(new_chunk.exists, timeout=300, message="new chunks")
        results = search_chunks(
            "extra content",
            filter_expr=f'file_id = "{new_id}"',
        )
        assert any(r["file_id"] == new_id for r in results)
    except Exception:
        dump_logs(compose_file, workdir)
        raise
    finally:
        stop(compose_file, workdir, env_file)
