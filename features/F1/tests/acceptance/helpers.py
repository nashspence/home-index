from __future__ import annotations

import shutil
import time
import logging
from datetime import datetime
from pathlib import Path
from typing import cast


def _expected_interval(cron: str) -> float:
    from apscheduler.triggers.cron import CronTrigger

    trigger = CronTrigger(**_parse_cron(cron))
    now = datetime.now(trigger.timezone)
    first = trigger.get_next_fire_time(None, now)
    if first is None:
        raise ValueError("CronTrigger failed to produce first fire time")
    second = trigger.get_next_fire_time(first, first)
    if second is None:
        raise ValueError("CronTrigger failed to produce second fire time")
    interval = (cast(datetime, second) - cast(datetime, first)).total_seconds()
    logging.getLogger(__name__).debug("expected interval %s -> %s", cron, interval)
    return interval


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
    log = logging.getLogger(__name__)
    log.debug("prepare dirs %s", workdir)
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
    logging.getLogger(__name__).debug("write env %s=%s", env_file, cron)
    env_file.write_text(f"CRON_EXPRESSION={cron}\n")


def _read_start_times(output_dir: Path) -> list[datetime]:
    log = logging.getLogger(__name__)
    if not (output_dir / "files.log").exists():
        log.debug("files.log not found in %s", output_dir)
        return []
    lines = (output_dir / "files.log").read_text().splitlines()
    stamps = [line.split(" [", 1)[0] for line in lines if "start file sync" in line]
    times = [datetime.strptime(s, "%Y-%m-%d %H:%M:%S,%f") for s in stamps]
    log.debug("read start times %s", times)
    return times


def _wait_for_start_lines(output_dir: Path, count: int) -> list[datetime]:
    deadline = time.time() + 120
    while True:
        times = _read_start_times(output_dir)
        if len(times) >= count:
            logging.getLogger(__name__).debug("found %d start lines", len(times))
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
                    logging.getLogger(__name__).debug("found log %s at %d", text, idx)
                    return idx
        if time.time() > deadline:
            raise AssertionError(f"Timed out waiting for log containing: {text}")
        time.sleep(0.5)
