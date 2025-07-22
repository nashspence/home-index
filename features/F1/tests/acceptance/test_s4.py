from __future__ import annotations

from pathlib import Path

from shared import compose, compose_paths, dump_logs

from .helpers import (
    _write_env,
    _prepare_dirs,
    _wait_for_start_lines,
    _expected_interval,
)


def test_f1s4(tmp_path: Path) -> None:
    compose_file, workdir, output_dir = compose_paths(__file__)
    env_file = tmp_path / ".env"
    cron = "*/2 * * * * *"
    _write_env(env_file, cron)
    _prepare_dirs(workdir, output_dir)
    compose(compose_file, workdir, "up", "-d", env_file=env_file)
    try:
        times = _wait_for_start_lines(output_dir, 3)
        compose(compose_file, workdir, "stop", env_file=env_file)
        interval = (times[-1] - times[-2]).total_seconds()
        expected = _expected_interval(cron)
        assert interval >= expected - 1
        assert interval <= expected * 3 + 1
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
