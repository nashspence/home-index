from __future__ import annotations

from pathlib import Path

from features.F2 import duplicate_finder
from shared import compose_paths, dump_logs, search_meili, wait_for

from .helpers import post_ops, put_file, start, stop


def test_f6s3(tmp_path: Path) -> None:
    compose_file, workdir, output_dir = compose_paths(__file__)
    env_file = tmp_path / ".env"
    start(compose_file, workdir, output_dir, env_file)
    try:
        file_a = tmp_path / "a.txt"
        file_a.write_text("hello")
        put_file(file_a, "a.txt")
        file_id = duplicate_finder.compute_hash(file_a)
        doc_dir = output_dir / "metadata" / "by-id" / file_id
        wait_for(doc_dir.exists, message="metadata")
        post_ops({"move": [{"src": "a.txt", "dest": "b.txt"}]})
        wait_for(lambda: (doc_dir / "document.json").exists(), message="moved")
        post_ops({"delete": ["b.txt"]})
        wait_for(lambda: not doc_dir.exists(), message="deleted")

        def _deleted() -> bool:
            try:
                search_meili(compose_file, workdir, f'id = "{file_id}"', timeout=1)
            except AssertionError:
                return True
            return False

        wait_for(_deleted, message="search delete")
    except Exception:
        dump_logs(compose_file, workdir)
        raise
    finally:
        stop(compose_file, workdir, env_file)
