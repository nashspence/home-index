from __future__ import annotations

from pathlib import Path

from shared import compose, compose_paths, dump_logs
import pytest

from .helpers import _write_env, _prepare_dirs, _read_start_times
from shared.acceptance import _start_server
from shared.acceptance import assert_event_sequence


@pytest.mark.asyncio
async def test_f1s5(tmp_path: Path) -> None:
    compose_file, workdir, output_dir = compose_paths(__file__)
    env_file = tmp_path / ".env"
    server, host, port = await _start_server()
    cron = "* * * * * *"
    _write_env(env_file, cron, TEST="true", TEST_LOG_TARGET=f"{host}:{port}")
    _prepare_dirs(workdir, output_dir)
    compose(compose_file, workdir, "up", "-d", env_file=env_file)
    try:
        reader, writer = await server.accept()
        expected = [
            {"event": "log-subscriber-attached"},
            {"event": "start file sync"},
            {"event": "completed file sync"},
        ]
        await assert_event_sequence(reader, writer, expected)

        assert len(_read_start_times(output_dir)) == 1
        expected = [{"event": "start file sync"}]
        await assert_event_sequence(reader, writer, expected)
        times = _read_start_times(output_dir)
        assert times[-1] > times[0]
        writer.close()
        await writer.wait_closed()
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
