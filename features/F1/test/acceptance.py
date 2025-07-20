from __future__ import annotations

import shutil
import time
from datetime import datetime
from pathlib import Path
from typing import cast

from apscheduler.triggers.cron import CronTrigger

from shared import compose, compose_paths, dump_logs, search_meili, wait_for


def _expected_interval(cron: str) -> float:
    trigger = CronTrigger(**_parse_cron(cron))
    now = datetime.now(trigger.timezone)
    first = trigger.get_next_fire_time(None, now)
    if first is None:
        raise ValueError("CronTrigger failed to produce first fire time")
    second = trigger.get_next_fire_time(first, first)
    if second is None:
        raise ValueError("CronTrigger failed to produce second fire time")
    return (cast(datetime, second) - cast(datetime, first)).total_seconds()


def _parse_cron(cron: str) -> dict[str, str]:
    parts = cron.split()
    if len(parts) == 5:
        return {
            "minute": parts[0],
            "hour": parts[1],
            "day": parts[2],
            "month": parts[3],
            "day_of_week": parts[4],
        }
    if len(parts) == 6:
        return {
            "second": parts[0],
            "minute": parts[1],
            "hour": parts[2],
            "day": parts[3],
            "month": parts[4],
            "day_of_week": parts[5],
        }
    raise ValueError("cron must have 5 or 6 fields")


def _prepare_dirs(workdir: Path, output_dir: Path, *, with_input: bool = True) -> None:
    if output_dir.exists():
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True)
    (output_dir / "modules_config.json").write_text('{"modules": []}')
    input_dir = workdir / "input"
    if input_dir.exists():
        shutil.rmtree(input_dir)
    if with_input:
        shutil.copytree(Path(__file__).with_name("input"), input_dir)
    else:
        input_dir.mkdir()


def _write_env(env_file: Path, cron: str) -> None:
    env_file.write_text(f"CRON_EXPRESSION={cron}\n")


def _read_start_times(output_dir: Path) -> list[datetime]:
    if not (output_dir / "files.log").exists():
        return []
    lines = (output_dir / "files.log").read_text().splitlines()
    stamps = [line.split(" [", 1)[0] for line in lines if "start file sync" in line]
    return [datetime.strptime(s, "%Y-%m-%d %H:%M:%S,%f") for s in stamps]


def _wait_for_start_lines(output_dir: Path, count: int) -> list[datetime]:
    deadline = time.time() + 120
    while True:
        times = _read_start_times(output_dir)
        if len(times) >= count:
            return times
        if time.time() > deadline:
            raise AssertionError("Timed out waiting for sync logs")
        time.sleep(0.5)


def _wait_for_log(output_dir: Path, text: str, start: int = 0) -> int:
    deadline = time.time() + 120
    while True:
        if (output_dir / "files.log").exists():
            lines = (output_dir / "files.log").read_text().splitlines()
            for idx, line in enumerate(lines[start:], start=start):
                if text in line:
                    return idx
        if time.time() > deadline:
            raise AssertionError(f"Timed out waiting for log containing: {text}")
        time.sleep(0.5)


def test_s1_initial_run_existing_files_indexed(tmp_path: Path) -> None:
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


def test_s2_new_file_appears_mid_run(tmp_path: Path) -> None:
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
        (workdir / "input" / "new.txt").write_text("new")
        _wait_for_start_lines(output_dir, 2)
        _wait_for_log(output_dir, "completed file sync", start=first_done + 1)
        wait_for(
            lambda: len(set(p.name for p in by_id.iterdir()) - existing) >= 1,
            message="new file indexed",
        )
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


def test_s3_file_contents_change(tmp_path: Path) -> None:
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


def test_s4_regular_cadence_honoured(tmp_path: Path) -> None:
    compose_file, workdir, output_dir = compose_paths(__file__)
    env_file = tmp_path / ".env"
    cron = "*/2 * * * * *"
    _write_env(env_file, cron)
    _prepare_dirs(workdir, output_dir)
    compose(compose_file, workdir, "up", "-d", env_file=env_file)
    try:
        times = _wait_for_start_lines(output_dir, 3)
        compose(compose_file, workdir, "stop", env_file=env_file)
        interval = (times[-1] - times[-2]).total_seconds()
        expected = _expected_interval(cron)
        assert interval >= expected - 1
        assert interval <= expected * 3 + 1
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


def test_s5_long_running_sync_never_overlaps(tmp_path: Path) -> None:
    compose_file, workdir, output_dir = compose_paths(__file__)
    env_file = tmp_path / ".env"
    cron = "* * * * * *"
    _write_env(env_file, cron)
    _prepare_dirs(workdir, output_dir)
    compose(compose_file, workdir, "up", "-d", env_file=env_file)
    try:
        _wait_for_start_lines(output_dir, 1)
        done_idx = _wait_for_log(output_dir, "completed file sync")
        assert len(_read_start_times(output_dir)) == 1
        _wait_for_start_lines(output_dir, 2)
        assert done_idx < _wait_for_log(
            output_dir, "start file sync", start=done_idx + 1
        )
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


def test_s6_change_schedule(tmp_path: Path) -> None:
    compose_file, workdir, output_dir = compose_paths(__file__)
    env_file = tmp_path / ".env"
    cron1 = "* * * * * *"
    _write_env(env_file, cron1)
    _prepare_dirs(workdir, output_dir)
    compose(compose_file, workdir, "up", "-d", env_file=env_file)
    try:
        _wait_for_start_lines(output_dir, 2)
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
    cron2 = "*/2 * * * * *"
    _write_env(env_file, cron2)
    initial_count = len(_read_start_times(output_dir))
    compose(compose_file, workdir, "up", "-d", env_file=env_file)
    try:
        times = _wait_for_start_lines(output_dir, initial_count + 2)
        interval = (times[-1] - times[-2]).total_seconds()
        expected = _expected_interval(cron2)
        assert abs(interval - expected) <= 1
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


def test_s7_restart_with_same_schedule(tmp_path: Path) -> None:
    compose_file, workdir, output_dir = compose_paths(__file__)
    env_file = tmp_path / ".env"
    cron = "* * * * * *"
    _write_env(env_file, cron)
    _prepare_dirs(workdir, output_dir)
    compose(compose_file, workdir, "up", "-d", env_file=env_file)
    try:
        _wait_for_start_lines(output_dir, 2)
        initial_lines = (output_dir / "files.log").read_text().splitlines()
        initial_count = len(_read_start_times(output_dir))
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
    compose(compose_file, workdir, "up", "-d", env_file=env_file)
    try:
        _wait_for_start_lines(output_dir, initial_count + 2)
        final_lines = (output_dir / "files.log").read_text().splitlines()
        assert len(final_lines) > len(initial_lines)
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


def test_s8_invalid_cron_blocks_startup(tmp_path: Path) -> None:
    compose_file, workdir, output_dir = compose_paths(__file__)
    env_file = tmp_path / ".env"
    _write_env(env_file, "bad cron")
    _prepare_dirs(workdir, output_dir)
    compose(compose_file, workdir, "up", "-d", env_file=env_file, check=False)
    try:
        wait_for(
            lambda: b"invalid cron expression"
            in compose(
                compose_file,
                workdir,
                "logs",
                "--no-color",
                env_file=env_file,
                check=False,
            ).stdout.lower(),
            timeout=180,
            message="error log",
        )
        wait_for(
            lambda: b"exit"
            in compose(
                compose_file, workdir, "ps", env_file=env_file, check=False
            ).stdout.lower(),
            timeout=60,
            message="container exit",
        )
        ps = compose(compose_file, workdir, "ps", env_file=env_file, check=False)
        assert b"exit" in ps.stdout.lower()
        logs = compose(
            compose_file, workdir, "logs", "--no-color", env_file=env_file, check=False
        )
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
