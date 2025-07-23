from __future__ import annotations

from pathlib import Path

import logging
from shared import compose, compose_paths, dump_logs, wait_for

from .helpers import (
    _write_env,
    _prepare_dirs,
    _wait_for_start_lines,
    _wait_for_log,
)

logger = logging.getLogger(__name__)


def test_f1s2(tmp_path: Path) -> None:
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
        first_done = _wait_for_log(output_dir, "completed file sync")
        logger.debug("first complete")
        by_id = output_dir / "metadata" / "by-id"
        wait_for(lambda: by_id.exists() and any(by_id.iterdir()), message="metadata")
        logger.debug("metadata ready")
        existing = {p.name for p in by_id.iterdir()}
        (workdir / "input" / "new.txt").write_text("new")
        logger.debug("new file written")
        _wait_for_start_lines(output_dir, 2)
        logger.debug("second start line")
        _wait_for_log(output_dir, "completed file sync", start=first_done + 1)
        logger.debug("second complete")
        wait_for(
            lambda: len(set(p.name for p in by_id.iterdir()) - existing) >= 1,
            message="new file indexed",
        )
        logger.debug("new file indexed")
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
