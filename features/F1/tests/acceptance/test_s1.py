from __future__ import annotations

from pathlib import Path

import logging
from shared import compose, compose_paths, dump_logs, search_meili, wait_for

from .helpers import (
    _write_env,
    _prepare_dirs,
    _wait_for_start_lines,
)

logger = logging.getLogger(__name__)


def test_f1s1(tmp_path: Path) -> None:
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
        wait_for(lambda: (output_dir / "files.log").exists(), message="files.log")
        logger.debug("files.log appeared")
        _wait_for_start_lines(output_dir, 2)
        logger.debug("two start lines")
        by_id = output_dir / "metadata" / "by-id"
        wait_for(lambda: by_id.exists() and any(by_id.iterdir()), message="metadata")
        logger.debug("metadata exists")
        assert search_meili(compose_file, workdir, "")
        logger.debug("search meili ok")
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
