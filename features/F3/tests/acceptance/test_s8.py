from __future__ import annotations

from pathlib import Path

from shared import compose, compose_paths, dump_logs

from .helpers import _run_once


def test_f3s8(tmp_path: Path) -> None:
    compose_file, workdir, output_dir = compose_paths(__file__)

    def setup(input_dir: Path) -> None:
        archive = input_dir / "archive"
        archive.mkdir()
        (archive / "drive1-status-ready").write_text("old")
        drive = input_dir / "archive" / "drive2"
        drive.mkdir(parents=True)
        (drive / "foo.txt").write_text("hi")

    try:
        _run_once(
            compose_file,
            workdir,
            output_dir,
            ["archive/drive2/foo.txt"],
            setup,
            override_ids={"archive/drive2/foo.txt": "hash1"},
        )
        old_marker = workdir / "input" / "archive" / "drive1-status-ready"
        new_marker = workdir / "input" / "archive" / "drive2-status-ready"
        assert not old_marker.exists()
        assert new_marker.exists()
        link = output_dir / "metadata" / "by-path" / "archive" / "drive2" / "foo.txt"
        assert link.is_symlink()
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
