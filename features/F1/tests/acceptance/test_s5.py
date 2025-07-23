from __future__ import annotations

from pathlib import Path

import logging
from shared import compose, compose_paths, dump_logs

from .helpers import (
    _write_env,
    _prepare_dirs,
    _wait_for_start_lines,
    _wait_for_log,
    _read_start_times,
)

logger = logging.getLogger(__name__)


def test_f1s5(tmp_path: Path) -> None:
    compose_file, workdir, output_dir = compose_paths(__file__)
    logger.debug("compose paths resolved")
    env_file = tmp_path / ".env"
    cron = "* * * * * *"
    _write_env(env_file, cron)
    logger.debug("env written")
    _prepare_dirs(workdir, output_dir)
    logger.debug("dirs prepared")
    compose(compose_file, workdir, "up", "-d", env_file=env_file)
    logger.debug("compose up")
    try:
        _wait_for_start_lines(output_dir, 1)
        logger.debug("first start line")
        done_idx = _wait_for_log(output_dir, "completed file sync")
        logger.debug("first complete")
        assert len(_read_start_times(output_dir)) == 1
        _wait_for_start_lines(output_dir, 2)
        logger.debug("second start line")
        assert done_idx < _wait_for_log(
            output_dir, "start file sync", start=done_idx + 1
        )
        logger.debug("no overlap confirmed")
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
