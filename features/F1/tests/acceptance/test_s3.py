from __future__ import annotations

from pathlib import Path

from shared import compose, compose_paths, dump_logs, wait_for

from .helpers import (
    _write_env,
    _prepare_dirs,
    _wait_for_start_lines,
    _wait_for_log,
)


def test_f1s3(tmp_path: Path) -> None:
    compose_file, workdir, output_dir = compose_paths(__file__)
    env_file = tmp_path / ".env"
    cron = "* * * * * *"
    _write_env(env_file, cron)
    _prepare_dirs(workdir, output_dir)
    compose(compose_file, workdir, "up", "-d", env_file=env_file)
    try:
        _wait_for_start_lines(output_dir, 1)
        first_done = _wait_for_log(output_dir, "completed file sync")
        by_id = output_dir / "metadata" / "by-id"
        wait_for(lambda: by_id.exists() and any(by_id.iterdir()), message="metadata")
        existing = {p.name for p in by_id.iterdir()}
        hello = workdir / "input" / "hello.txt"
        hello.write_text("changed")
        _wait_for_start_lines(output_dir, 2)
        _wait_for_log(output_dir, "completed file sync", start=first_done + 1)
        wait_for(
            lambda: len(set(p.name for p in by_id.iterdir()) - existing) >= 1,
            message="new hash",
        )
        assert existing <= {p.name for p in by_id.iterdir()}
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
