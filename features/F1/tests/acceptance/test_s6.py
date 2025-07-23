from __future__ import annotations

from pathlib import Path

import logging
from shared import compose, compose_paths, dump_logs

from .helpers import (
    _write_env,
    _prepare_dirs,
    _wait_for_start_lines,
    _read_start_times,
    _expected_interval,
)

logger = logging.getLogger(__name__)


def test_f1s6(tmp_path: Path) -> None:
    compose_file, workdir, output_dir = compose_paths(__file__)
    logger.debug("compose paths resolved")
    env_file = tmp_path / ".env"
    cron1 = "* * * * * *"
    _write_env(env_file, cron1)
    logger.debug("env1 written")
    _prepare_dirs(workdir, output_dir)
    logger.debug("dirs prepared")
    compose(compose_file, workdir, "up", "-d", env_file=env_file)
    logger.debug("compose up first")
    try:
        _wait_for_start_lines(output_dir, 2)
        logger.debug("first run complete")
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
    cron2 = "*/2 * * * * *"
    _write_env(env_file, cron2)
    logger.debug("env2 written")
    initial_count = len(_read_start_times(output_dir))
    compose(compose_file, workdir, "up", "-d", env_file=env_file)
    logger.debug("compose up second")
    try:
        times = _wait_for_start_lines(output_dir, initial_count + 3)
        logger.debug("times %s", times)
        interval = (times[-1] - times[-2]).total_seconds()
        expected = _expected_interval(cron2)
        assert abs(interval - expected) <= 1
        logger.debug("interval %s expected %s", interval, expected)
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
