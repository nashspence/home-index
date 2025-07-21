from __future__ import annotations

from pathlib import Path

from shared import compose, compose_paths, dump_logs

from .helpers import (
    _write_env,
    _prepare_dirs,
    _wait_for_start_lines,
    _wait_for_log,
    _read_start_times,
)


def f1s5(tmp_path: Path) -> None:
    compose_file, workdir, output_dir = compose_paths(__file__)
    env_file = tmp_path / ".env"
    cron = "* * * * * *"
    _write_env(env_file, cron)
    _prepare_dirs(workdir, output_dir)
    compose(compose_file, workdir, "up", "-d", env_file=env_file)
    try:
        _wait_for_start_lines(output_dir, 1)
        done_idx = _wait_for_log(output_dir, "completed file sync")
        assert len(_read_start_times(output_dir)) == 1
        _wait_for_start_lines(output_dir, 2)
        assert done_idx < _wait_for_log(
            output_dir, "start file sync", start=done_idx + 1
        )
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
