import shutil
import subprocess
import time
from datetime import datetime
from pathlib import Path

from apscheduler.triggers.cron import CronTrigger


def _expected_interval(cron: str) -> float:
    trigger = CronTrigger.from_crontab(cron)
    now = datetime.now(trigger.timezone)
    first = trigger.get_next_fire_time(None, now)
    second = trigger.get_next_fire_time(first, first)
    return (second - first).total_seconds()


def _run_once(
    compose_file: Path, workdir: Path, output_dir: Path, env_file: Path, cron: str
) -> None:
    if output_dir.exists():
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True)
    env_file.write_text(f"CRON_EXPRESSION={cron}\n")

    subprocess.run(
        [
            "docker",
            "compose",
            "--env-file",
            str(env_file),
            "-f",
            str(compose_file),
            "up",
            "-d",
        ],
        check=True,
        cwd=workdir,
    )
    try:
        start = time.time()
        expected_interval = _expected_interval(cron)
        # Allow ample time for container startup and at least two sync cycles.
        deadline = start + expected_interval * 3 + 120
        timestamps: list[str] = []
        while True:
            time.sleep(5)
            if (output_dir / "files.log").exists():
                logs = (output_dir / "files.log").read_text().splitlines()
                timestamps = [
                    line.split(" [", 1)[0] for line in logs if "start file sync" in line
                ]
                if len(timestamps) >= 2:
                    break
            if time.time() > deadline:
                raise AssertionError("Timed out waiting for sync logs")
        subprocess.run(
            [
                "docker",
                "compose",
                "--env-file",
                str(env_file),
                "-f",
                str(compose_file),
                "stop",
            ],
            check=True,
            cwd=workdir,
        )
        times = [datetime.strptime(t, "%Y-%m-%d %H:%M:%S,%f") for t in timestamps[:2]]
        assert (times[1] - times[0]).total_seconds() >= expected_interval
        by_id = output_dir / "metadata" / "by-id"
        assert any(by_id.iterdir())
    except Exception:
        subprocess.run(
            [
                "docker",
                "compose",
                "--env-file",
                str(env_file),
                "-f",
                str(compose_file),
                "logs",
                "--no-color",
            ],
            check=False,
            cwd=workdir,
        )
        if (output_dir / "files.log").exists():
            print("--- files.log ---")
            print((output_dir / "files.log").read_text())
        raise
    finally:
        subprocess.run(
            [
                "docker",
                "compose",
                "--env-file",
                str(env_file),
                "-f",
                str(compose_file),
                "rm",
                "-fsv",
            ],
            check=False,
            cwd=workdir,
        )


def test_indexing_runs_on_schedule(tmp_path: Path) -> None:
    compose_file = Path(__file__).with_name("docker-compose.yml")
    workdir = compose_file.parent
    output_dir = workdir / "output"
    env_file = tmp_path / ".env"
    for cron in ["* * * * *", "*/2 * * * *"]:
        _run_once(compose_file, workdir, output_dir, env_file, cron)
