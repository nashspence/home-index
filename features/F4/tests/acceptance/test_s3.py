from __future__ import annotations

from pathlib import Path

from shared import compose_paths

from .helpers import _run_remove_drive_mid, _run_again


def test_f4s3(tmp_path: Path) -> None:
    compose_file, workdir, output_dir = compose_paths(__file__)
    env_file = tmp_path / ".env"
    drive = workdir / "input" / "archive" / "drive1"
    drive.mkdir(parents=True)
    (drive / "a.txt").write_text("a")
    (drive / "b.txt").write_text("b")
    marker_pending = workdir / "input" / "archive" / "drive1-status-pending"
    marker_pending.write_text("old")
    doc_a, doc_b = _run_remove_drive_mid(compose_file, workdir, output_dir, env_file)
    version_b = (
        output_dir / "metadata" / "by-id" / doc_b / "example-module" / "version.json"
    )
    assert not version_b.exists()
    assert marker_pending.exists()
    drive.mkdir(parents=True)
    (drive / "b.txt").write_text("b")
    _run_again(compose_file, workdir, output_dir, env_file)
    assert version_b.exists()
    ready = workdir / "input" / "archive" / "drive1-status-ready"
    assert ready.exists()
