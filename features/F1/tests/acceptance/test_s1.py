from __future__ import annotations

from pathlib import Path

from shared import compose, compose_paths, dump_logs, search_meili
import pytest

from .helpers import _write_env, _prepare_dirs
from shared.acceptance import _start_server
from shared.acceptance import assert_event_sequence


@pytest.mark.asyncio
async def test_f1s1(tmp_path: Path) -> None:
    compose_file, workdir, output_dir = compose_paths(__file__)
    env_file = tmp_path / ".env"
    server, host, port = await _start_server()
    cron = "* * * * * *"
    _write_env(env_file, cron, TEST="true", TEST_LOG_TARGET=f"http://{host}:{port}")
    _prepare_dirs(workdir, output_dir)
    compose(compose_file, workdir, "up", "-d", env_file=env_file)
    writer = None
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
        by_id = output_dir / "metadata" / "by-id"
        assert by_id.exists() and any(by_id.iterdir())
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
        if writer is not None:
            writer.close()
            await writer.wait_closed()
        server.close()
        await server.wait_closed()
