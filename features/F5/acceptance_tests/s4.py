from __future__ import annotations

from pathlib import Path
import json

from shared import compose_paths, dump_logs

from .helpers import prepare_dirs, start, stop, write_env, wait_initial
from features.F2 import duplicate_finder


def f5s4(tmp_path: Path) -> None:
    compose_file, workdir, output_dir = compose_paths(__file__)
    env_file = tmp_path / ".env"
    prepare_dirs(workdir, output_dir)
    write_env(env_file)

    doc_path = workdir / "input" / "snippet.txt"
    doc_id = duplicate_finder.compute_hash(doc_path)

    start(compose_file, workdir, env_file)
    try:
        chunk_file = wait_initial(compose_file, workdir, doc_id, env_file)
        chunks = json.loads(chunk_file.read_text())
        required = {
            "id",
            "file_id",
            "module",
            "text",
            "index",
            "char_offset",
            "char_length",
        }
        for c in chunks:
            assert required <= set(c)
            assert all(c[f] is not None for f in required)
    except Exception:
        dump_logs(compose_file, workdir)
        raise
    finally:
        stop(compose_file, workdir, env_file)
