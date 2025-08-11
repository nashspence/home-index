from __future__ import annotations

from pathlib import Path
import pytest

from shared import compose, compose_paths, dump_logs, search_meili

from .helpers import _run_once


def test_f3s4(tmp_path: Path) -> None:
    compose_file, workdir, output_dir = compose_paths(__file__)
    ts = "2025-01-01T00:00:00Z"

    def setup(input_dir: Path) -> None:
        drive = input_dir / "archive" / "drive1"
        drive.mkdir(parents=True)
        (input_dir / "archive" / "drive1-status-ready").write_text(ts)

    try:
        file_id = "hash1"
        _run_once(
            compose_file,
            workdir,
            output_dir,
            [],
            setup,
        )
        marker = workdir / "input" / "archive" / "drive1-status-ready"
        ts_new = marker.read_text()
        assert ts_new != ts
        with pytest.raises(AssertionError):
            search_meili(compose_file, workdir, f'id = "{file_id}"', timeout=5)
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
