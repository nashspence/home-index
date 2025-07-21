from __future__ import annotations

from pathlib import Path

from shared import compose, compose_paths, dump_logs, search_meili

from .helpers import _run_once, _run_sync


def f3s10(tmp_path: Path) -> None:
    compose_file, workdir, output_dir = compose_paths(__file__)

    def setup(input_dir: Path) -> None:
        drive = input_dir / "archive" / "drive1"
        drive.mkdir(parents=True)
        (drive / "foo.txt").write_text("hi")

    try:
        ids = _run_once(
            compose_file,
            workdir,
            output_dir,
            ["archive/drive1/foo.txt"],
            setup,
        )
        file_id = ids[0]

        compose(
            compose_file, workdir, "down", "--volumes", "--rmi", "local", check=False
        )

        input_dir = workdir / "input"
        (input_dir / "archive").rename(input_dir / "archive2")
        env_file = tmp_path / ".env"
        env_file.write_text("ARCHIVE_DIRECTORY=/files/archive2\n")

        _run_sync(
            compose_file,
            workdir,
            output_dir,
            [file_id],
            env_file=env_file,
        )

        new_link = (
            output_dir / "metadata" / "by-path" / "archive2" / "drive1" / "foo.txt"
        )
        old_link = (
            output_dir / "metadata" / "by-path" / "archive" / "drive1" / "foo.txt"
        )
        assert new_link.is_symlink()
        assert not old_link.exists()
        marker = workdir / "input" / "archive2" / "drive1-status-ready"
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
