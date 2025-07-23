from __future__ import annotations

from pathlib import Path

import logging
from shared import compose, compose_paths, dump_logs, wait_for

from .helpers import (
    _write_env,
    _prepare_dirs,
)

logger = logging.getLogger(__name__)


def test_f1s8(tmp_path: Path) -> None:
    compose_file, workdir, output_dir = compose_paths(__file__)
    logger.debug("compose paths resolved")
    env_file = tmp_path / ".env"
    _write_env(env_file, "bad cron")
    logger.debug("env written")
    _prepare_dirs(workdir, output_dir)
    logger.debug("dirs prepared")
    compose(compose_file, workdir, "up", "-d", env_file=env_file, check=False)
    logger.debug("compose up")
    try:
        wait_for(
            lambda: b"invalid cron expression"
            in compose(
                compose_file,
                workdir,
                "logs",
                "--no-color",
                check=False,
            ).stdout.lower(),
            timeout=60,
            message="error log",
        )
        logger.debug("invalid cron logged")
        wait_for(
            lambda: b"up"
            not in compose(
                compose_file,
                workdir,
                "ps",
                "home-index",
                check=False,
            ).stdout.lower(),
            timeout=60,
            message="container stopped",
        )
        logger.debug("container stopped")
        ps = compose(compose_file, workdir, "ps", "home-index", check=False)
        assert (
            b"exit" in ps.stdout.lower()
            or b"exited" in ps.stdout.lower()
            or b"up" not in ps.stdout.lower()
        )
        logs = compose(compose_file, workdir, "logs", "--no-color", check=False)
        assert b"invalid cron expression" in logs.stdout.lower()
        logger.debug("error confirmed")
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
