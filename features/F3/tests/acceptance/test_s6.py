from __future__ import annotations

from pathlib import Path

from features.F2 import duplicate_finder
from shared import compose, compose_paths, dump_logs, search_meili

from .helpers import _run_once


def f3s6(tmp_path: Path) -> None:
    compose_file, workdir, output_dir = compose_paths(__file__)

    def setup(input_dir: Path) -> None:
        drive = input_dir / "archive" / "drive1"
        drive.mkdir(parents=True)
        (drive / "baz.txt").write_text("hi")
        (input_dir / "baz.txt").write_text("hi")

    try:
        _run_once(
            compose_file,
            workdir,
            output_dir,
            ["archive/drive1/baz.txt", "baz.txt"],
            setup,
        )
        doc_id = duplicate_finder.compute_hash(workdir / "input" / "baz.txt")
        by_id = output_dir / "metadata" / "by-id" / doc_id
        assert by_id.exists()
        docs = search_meili(compose_file, workdir, f'id = "{doc_id}"')
        assert all(not doc["offline"] for doc in docs)
        ready = workdir / "input" / "archive" / "drive1-status-ready"
        assert ready.exists()
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
