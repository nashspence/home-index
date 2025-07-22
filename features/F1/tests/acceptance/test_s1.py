from __future__ import annotations

from pathlib import Path

from shared import compose, compose_paths, dump_logs, search_meili, wait_for

from .helpers import (
    _write_env,
    _prepare_dirs,
    _wait_for_start_lines,
)


def test_f1s1(tmp_path: Path) -> None:
    compose_file, workdir, output_dir = compose_paths(__file__)
    env_file = tmp_path / ".env"
    cron = "* * * * * *"
    _write_env(env_file, cron)
    _prepare_dirs(workdir, output_dir)
    compose(compose_file, workdir, "up", "-d", env_file=env_file)
    try:
        wait_for(lambda: (output_dir / "files.log").exists(), message="files.log")
        _wait_for_start_lines(output_dir, 2)
        by_id = output_dir / "metadata" / "by-id"
        wait_for(lambda: by_id.exists() and any(by_id.iterdir()), message="metadata")
        assert search_meili(compose_file, workdir, "")
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
