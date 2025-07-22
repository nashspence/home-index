from __future__ import annotations

from pathlib import Path

from shared import compose, compose_paths, dump_logs

from .helpers import (
    _write_env,
    _prepare_dirs,
    _wait_for_start_lines,
    _read_start_times,
)


def test_f1s7(tmp_path: Path) -> None:
    compose_file, workdir, output_dir = compose_paths(__file__)
    env_file = tmp_path / ".env"
    cron = "* * * * * *"
    _write_env(env_file, cron)
    _prepare_dirs(workdir, output_dir)
    compose(compose_file, workdir, "up", "-d", env_file=env_file)
    try:
        _wait_for_start_lines(output_dir, 2)
        initial_lines = (output_dir / "files.log").read_text().splitlines()
        initial_count = len(_read_start_times(output_dir))
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
            env_file=env_file,
            check=False,
        )
    compose(compose_file, workdir, "up", "-d", env_file=env_file)
    try:
        _wait_for_start_lines(output_dir, initial_count + 2)
        final_lines = (output_dir / "files.log").read_text().splitlines()
        assert len(final_lines) > len(initial_lines)
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
            env_file=env_file,
            check=False,
        )
