from __future__ import annotations

import json
from pathlib import Path

from features.F2 import duplicate_finder
from shared import compose_paths, dump_logs, search_meili, wait_for

from .helpers import post_ops, put_file, start, stop


def f6s4(tmp_path: Path) -> None:
    compose_file, workdir, output_dir = compose_paths(__file__)
    env_file = tmp_path / ".env"
    start(compose_file, workdir, output_dir, env_file)
    try:
        file_c = tmp_path / "c.txt"
        file_d = tmp_path / "d.txt"
        file_c.write_text("c")
        file_d.write_text("d")
        put_file(file_c, "c.txt")
        put_file(file_d, "d.txt")
        file_c_id = duplicate_finder.compute_hash(file_c)
        file_d_id = duplicate_finder.compute_hash(file_d)
        doc_c = output_dir / "metadata" / "by-id" / file_c_id
        doc_d = output_dir / "metadata" / "by-id" / file_d_id
        wait_for(doc_c.exists, message="metadata c")
        wait_for(doc_d.exists, message="metadata d")
        post_ops({"move": [{"src": "c.txt", "dest": "e.txt"}], "delete": ["d.txt"]})

        def _moved() -> bool:
            with open(doc_c / "document.json") as fh:
                doc = json.load(fh)
            return "e.txt" in doc.get("paths", {})

        wait_for(_moved, message="moved c")
        wait_for(lambda: not doc_d.exists(), message="deleted d")
        wait_for(
            lambda: bool(search_meili(compose_file, workdir, f'id = "{file_c_id}"')),
            message="search c",
        )

        def _gone() -> bool:
            try:
                search_meili(compose_file, workdir, f'id = "{file_d_id}"', timeout=1)
            except AssertionError:
                return True
            return False

        wait_for(_gone, message="search d")
    except Exception:
        dump_logs(compose_file, workdir)
        raise
    finally:
        stop(compose_file, workdir, env_file)
