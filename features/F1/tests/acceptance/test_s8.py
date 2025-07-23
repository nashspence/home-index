from __future__ import annotations

from pathlib import Path

from shared import compose, compose_paths, dump_logs, wait_for
import pytest

from .helpers import _write_env, _prepare_dirs
from shared.acceptance import _start_server
from shared.acceptance import assert_event_sequence


@pytest.mark.asyncio
async def test_f1s8(tmp_path: Path) -> None:
    compose_file, workdir, output_dir = compose_paths(__file__)
    env_file = tmp_path / ".env"
    server, host, port = await _start_server()
    _write_env(env_file, "bad cron", TEST="true", TEST_LOG_TARGET=f"{host}:{port}")
    _prepare_dirs(workdir, output_dir)
    compose(compose_file, workdir, "up", "-d", env_file=env_file, check=False)
    try:
        reader, writer = await server.accept()
        await assert_event_sequence(
            reader,
            writer,
            [{"event": "log-subscriber-attached"}],
        )
        writer.close()
        await writer.wait_closed()
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
        ps = compose(compose_file, workdir, "ps", "home-index", check=False)
        assert (
            b"exit" in ps.stdout.lower()
            or b"exited" in ps.stdout.lower()
            or b"up" not in ps.stdout.lower()
        )
        logs = compose(compose_file, workdir, "logs", "--no-color", check=False)
        assert b"invalid cron expression" in logs.stdout.lower()
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
        server.close()
        await server.wait_closed()
