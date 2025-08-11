from __future__ import annotations

from pathlib import Path

from shared import compose, compose_paths, dump_logs, search_meili

from .helpers import _run_once


def test_f3s1(tmp_path: Path) -> None:
    compose_file, workdir, output_dir = compose_paths(__file__)

    def setup(input_dir: Path) -> None:
        drive = input_dir / "archive" / "drive1"
        drive.mkdir(parents=True)
        (drive / "foo.txt").write_text("hi")

    try:
        ids = _run_once(
            compose_file, workdir, output_dir, ["archive/drive1/foo.txt"], setup
        )
        file_id = ids[0]
        marker = workdir / "input" / "archive" / "drive1-status-ready"
        assert marker.exists()
        docs = search_meili(compose_file, workdir, f'id = "{file_id}"')
        assert all(not doc["offline"] for doc in docs)
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
