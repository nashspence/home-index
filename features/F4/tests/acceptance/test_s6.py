from __future__ import annotations

from pathlib import Path

from shared import compose_paths

from .helpers import _run_files


def test_f4s6(tmp_path: Path) -> None:
    compose_file, workdir, output_dir = compose_paths(__file__)
    env_file = tmp_path / ".env"
    drive = workdir / "input" / "archive" / "drive1"
    drive.mkdir(parents=True)
    (drive / "a.txt").write_text("a")
    regular = workdir / "input" / "b.txt"
    regular.write_text("b")
    marker = workdir / "input" / "archive" / "drive1-status-ready"
    marker.write_text("old")
    version_files = _run_files(
        compose_file,
        workdir,
        output_dir,
        env_file,
        ["archive/drive1/a.txt", "b.txt"],
    )
    archive_version = version_files[0]
    regular_version = version_files[1]
    assert regular_version.stat().st_mtime >= archive_version.stat().st_mtime
    assert marker.read_text() != "old"
