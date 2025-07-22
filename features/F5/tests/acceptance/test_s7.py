from __future__ import annotations

from pathlib import Path
import json

from shared import compose_paths, dump_logs

from .helpers import prepare_dirs, start, stop, write_env, wait_initial
from features.F2 import duplicate_finder


def f5s7(tmp_path: Path) -> None:
    compose_file, workdir, output_dir = compose_paths(__file__)
    env_file = tmp_path / ".env"
    prepare_dirs(workdir, output_dir)
    write_env(env_file, {"EMBED_MODEL_NAME": "intfloat/e5-small-v2"})

    doc_path = workdir / "input" / "snippet.txt"
    doc_id = duplicate_finder.compute_hash(doc_path)

    start(compose_file, workdir, env_file)
    try:
        chunk_file = wait_initial(compose_file, workdir, doc_id, env_file)
        mtime1 = chunk_file.stat().st_mtime
        content = chunk_file.with_name("content.json").read_text()
        log_file = chunk_file.with_name("log.txt")
        start_count1 = log_file.read_text().count("start")
        settings1 = json.loads((output_dir / "chunk_settings.json").read_text())
        assert settings1["EMBED_MODEL_NAME"] == "intfloat/e5-small-v2"
    except Exception:
        dump_logs(compose_file, workdir)
        raise
    finally:
        stop(compose_file, workdir, env_file)

    write_env(env_file, {"EMBED_MODEL_NAME": "intfloat/e5-base"})
    start(compose_file, workdir, env_file)
    try:
        chunk_file = wait_initial(compose_file, workdir, doc_id, env_file)
        assert chunk_file.stat().st_mtime > mtime1
        assert chunk_file.with_name("content.json").read_text() == content
        log_file = chunk_file.with_name("log.txt")
        assert log_file.read_text().count("start") == start_count1
        settings2 = json.loads((output_dir / "chunk_settings.json").read_text())
        assert settings2["EMBED_MODEL_NAME"] == "intfloat/e5-base"
    except Exception:
        dump_logs(compose_file, workdir)
        raise
    finally:
        stop(compose_file, workdir, env_file)
