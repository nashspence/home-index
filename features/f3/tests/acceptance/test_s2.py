from __future__ import annotations

from pathlib import Path

from shared import compose, compose_paths, dump_logs, search_meili

from .helpers import _run_once


def test_f3s2(tmp_path: Path) -> None:
    compose_file, workdir, output_dir = compose_paths(__file__)
    ts = "2025-01-01T00:00:00Z"

    def setup(input_dir: Path) -> None:
        archive = input_dir / "archive"
        archive.mkdir()
        (archive / "drive1-status-ready").write_text(ts)

    try:
        file_id = "hash1"
        _run_once(
            compose_file,
            workdir,
            output_dir,
            ["archive/drive1/foo.txt"],
            setup,
            override_ids={"archive/drive1/foo.txt": file_id},
        )
        marker = workdir / "input" / "archive" / "drive1-status-ready"
        assert marker.read_text() == ts
        docs = search_meili(compose_file, workdir, f'id = "{file_id}"')
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
