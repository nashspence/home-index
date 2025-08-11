from __future__ import annotations

from pathlib import Path

from shared import compose_paths, dump_logs, wait_for

from .helpers import prepare_dirs, start, stop, write_env, wait_initial
from features.f2 import duplicate_finder


def test_f5s3(tmp_path: Path) -> None:
    compose_file, workdir, output_dir = compose_paths(__file__)
    env_file = tmp_path / ".env"
    prepare_dirs(workdir, output_dir)
    write_env(env_file)

    doc_path = workdir / "input" / "snippet.txt"
    orig_id = duplicate_finder.compute_hash(doc_path)

    start(compose_file, workdir, env_file)
    try:
        wait_initial(compose_file, workdir, orig_id, env_file)
        doc_path.write_text("changed text for scenario three")
        new_id = duplicate_finder.compute_hash(doc_path)
        new_chunk = (
            output_dir / "metadata" / "by-id" / new_id / "text-module" / "chunks.json"
        )
        wait_for(new_chunk.exists, timeout=300, message="new chunks")
        assert (output_dir / "metadata" / "by-id" / orig_id).exists()
    except Exception:
        dump_logs(compose_file, workdir)
        raise
    finally:
        stop(compose_file, workdir, env_file)
