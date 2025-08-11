from __future__ import annotations

from pathlib import Path

from shared import compose_paths

from .helpers import _run_once


def test_f4s1(tmp_path: Path) -> None:
    compose_file, workdir, output_dir = compose_paths(__file__)
    env_file = tmp_path / ".env"
    drive = workdir / "input" / "archive" / "drive1"
    drive.mkdir(parents=True)
    (drive / "foo.txt").write_text("hi")
    (workdir / "input" / "archive" / "drive1-status-pending").write_text("x")
    _run_once(
        compose_file,
        workdir,
        output_dir,
        env_file,
        file_name="archive/drive1/foo.txt",
    )
    ready = workdir / "input" / "archive" / "drive1-status-ready"
    assert ready.exists()
