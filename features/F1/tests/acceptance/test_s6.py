from __future__ import annotations

from pathlib import Path

from shared import compose, compose_paths, dump_logs
import pytest

from .helpers import _write_env, _prepare_dirs, _read_start_times, _expected_interval
from shared.acceptance import _start_server
from shared.acceptance import assert_event_sequence


@pytest.mark.asyncio
async def test_f1s6(tmp_path: Path) -> None:
    compose_file, workdir, output_dir = compose_paths(__file__)
    env_file = tmp_path / ".env"
    server, host, port = await _start_server()
    cron1 = "* * * * * *"
    _write_env(env_file, cron1, TEST="true", TEST_LOG_TARGET=f"http://{host}:{port}")
    _prepare_dirs(workdir, output_dir)
    compose(compose_file, workdir, "up", "-d", env_file=env_file)
    try:
        reader, writer = await server.accept(timeout=60)
        expected = [
            {"event": "log-subscriber-attached"},
            {"event": "start file sync"},
            {"event": "completed file sync"},
            {"event": "start file sync"},
            {"event": "completed file sync"},
        ]
        await assert_event_sequence(reader, writer, expected)
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
        writer.close()
        await writer.wait_closed()
        server.close()
        await server.wait_closed()
    cron2 = "*/2 * * * * *"
    server, host, port = await _start_server()
    _write_env(env_file, cron2, TEST="true", TEST_LOG_TARGET=f"http://{host}:{port}")
    initial_count = len(_read_start_times(output_dir))
    compose(compose_file, workdir, "up", "-d", env_file=env_file)
    try:
        reader, writer = await server.accept(timeout=60)
        needed = initial_count + 3 - len(_read_start_times(output_dir))
        expected = [{"event": "log-subscriber-attached"}] + (
            [{"event": "start file sync"}, {"event": "completed file sync"}] * needed
        )
        await assert_event_sequence(reader, writer, expected)
        times = _read_start_times(output_dir)
        interval = (times[-1] - times[-2]).total_seconds()
        expected_interval = _expected_interval(cron2)
        assert abs(interval - expected_interval) <= 1
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
