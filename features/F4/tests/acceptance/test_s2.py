from __future__ import annotations

from pathlib import Path

from shared import compose_paths

from .helpers import _run_once


def f4s2(tmp_path: Path) -> None:
    compose_file, workdir, output_dir = compose_paths(__file__)
    env_file = tmp_path / ".env"
    drive = workdir / "input" / "archive" / "drive1"
    drive.mkdir(parents=True)
    (drive / "foo.txt").write_text("hi")
    marker = workdir / "input" / "archive" / "drive1-status-ready"
    marker.write_text("old")
    _run_once(
        compose_file,
        workdir,
        output_dir,
        env_file,
        file_name="archive/drive1/foo.txt",
    )
    assert marker.read_text() != "old"
