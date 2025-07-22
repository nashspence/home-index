from __future__ import annotations

import json
from pathlib import Path

from features.F2 import duplicate_finder
from shared import compose_paths, dump_logs, search_meili, wait_for

from .helpers import move_dav, put_file, start, stop


def test_f6s5(tmp_path: Path) -> None:
    compose_file, workdir, output_dir = compose_paths(__file__)
    env_file = tmp_path / ".env"
    start(compose_file, workdir, output_dir, env_file)
    try:
        file_e = tmp_path / "e.txt"
        file_e.write_text("e")
        put_file(file_e, "e.txt")
        file_id = duplicate_finder.compute_hash(file_e)
        doc_dir = output_dir / "metadata" / "by-id" / file_id
        wait_for(doc_dir.exists, message="metadata")
        move_dav("e.txt", "f.txt")

        def _moved() -> bool:
            with open(doc_dir / "document.json") as fh:
                doc = json.load(fh)
            return "f.txt" in doc.get("paths", {}) and "e.txt" not in doc.get(
                "paths", {}
            )

        wait_for(_moved, message="moved via DAV")
        docs = search_meili(compose_file, workdir, f'id = "{file_id}"')
        assert all("f.txt" in doc["paths"] for doc in docs)
    except Exception:
        dump_logs(compose_file, workdir)
        raise
    finally:
        stop(compose_file, workdir, env_file)
