from __future__ import annotations

from pathlib import Path
import pytest

from shared import compose_paths, dump_logs, search_meili, wait_for

from .helpers import prepare_dirs, start, stop, write_env, wait_initial
from features.f2 import duplicate_finder


def test_f5s9(tmp_path: Path) -> None:
    compose_file, workdir, output_dir = compose_paths(__file__)
    env_file = tmp_path / ".env"
    prepare_dirs(workdir, output_dir)
    write_env(env_file)

    doc_path = workdir / "input" / "snippet.txt"
    doc_id = duplicate_finder.compute_hash(doc_path)

    start(compose_file, workdir, env_file)
    try:
        wait_initial(compose_file, workdir, doc_id, env_file)
    except Exception:
        dump_logs(compose_file, workdir)
        raise
    finally:
        stop(compose_file, workdir, env_file)

    doc_path.unlink()
    write_env(env_file)
    start(compose_file, workdir, env_file)
    try:
        with pytest.raises(AssertionError):
            search_meili(compose_file, workdir, f'id = "{doc_id}"', timeout=5)
        metadata_dir = output_dir / "metadata" / "by-id" / doc_id
        wait_for(lambda: not metadata_dir.exists(), message="metadata removed")
    except Exception:
        dump_logs(compose_file, workdir)
        raise
    finally:
        stop(compose_file, workdir, env_file)
