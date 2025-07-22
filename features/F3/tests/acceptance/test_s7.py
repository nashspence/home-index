from __future__ import annotations

import json
import os
from pathlib import Path

from shared import compose, compose_paths, dump_logs, search_meili

from .helpers import _run_once


def test_f3s7(tmp_path: Path) -> None:
    compose_file, workdir, output_dir = compose_paths(__file__)
    ts = "2025-01-01T00:00:00Z"

    def setup(input_dir: Path) -> None:
        archive_dir = input_dir / "archive"
        archive_dir.mkdir()
        (archive_dir / "drive1-status-ready").write_text(ts)
        doc_dir = output_dir / "metadata" / "by-id" / "hash1"
        doc_dir.mkdir(parents=True)
        doc = {
            "id": "hash1",
            "paths": {"archive/drive1/baz.txt": 1.0, "baz.txt": 1.0},
            "paths_list": ["archive/drive1/baz.txt", "baz.txt"],
            "mtime": 1.0,
            "size": 1,
            "type": "text/plain",
            "copies": 2,
            "version": 1,
            "next": "",
        }
        (doc_dir / "document.json").write_text(json.dumps(doc))
        link = output_dir / "metadata" / "by-path" / "archive" / "drive1" / "baz.txt"
        link.parent.mkdir(parents=True, exist_ok=True)
        relative_target = os.path.relpath(doc_dir, link.parent)
        link.symlink_to(relative_target, target_is_directory=True)
        link2 = output_dir / "metadata" / "by-path" / "baz.txt"
        link2.parent.mkdir(parents=True, exist_ok=True)
        relative_target2 = os.path.relpath(doc_dir, link2.parent)
        link2.symlink_to(relative_target2, target_is_directory=True)

    try:
        _run_once(
            compose_file,
            workdir,
            output_dir,
            [],
            setup,
            override_ids={},
        )
        marker = workdir / "input" / "archive" / "drive1-status-ready"
        assert marker.read_text() == ts
        docs = search_meili(compose_file, workdir, 'id = "hash1"')
        assert all(doc["offline"] for doc in docs)
    except Exception:
        dump_logs(compose_file, workdir)
        raise
    finally:
        compose(
            compose_file,
            workdir,
            "down",
            "--volumes",
            "--rmi",
            "local",
            check=False,
        )
