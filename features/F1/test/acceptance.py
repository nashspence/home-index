import shutil
import subprocess
import time
from datetime import datetime
from pathlib import Path


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
        time.sleep(70)
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
        logs = (output_dir / "files.log").read_text().splitlines()
        timestamps = [
            line.split(" [", 1)[0] for line in logs if "start file sync" in line
        ]
        assert len(timestamps) >= 2
        times = [datetime.strptime(t, "%Y-%m-%d %H:%M:%S,%f") for t in timestamps[:2]]
        assert (times[1] - times[0]).total_seconds() >= 60
        by_id = output_dir / "metadata" / "by-id"
        assert any(by_id.iterdir())
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
            check=True,
            cwd=workdir,
        )


def test_indexing_runs_on_schedule(tmp_path: Path) -> None:
    compose_file = Path(__file__).with_name("docker-compose.yml")
    workdir = compose_file.parent
    output_dir = workdir / "output"
    env_file = tmp_path / ".env"
    for cron in ["* * * * *", "*/2 * * * *"]:
        _run_once(compose_file, workdir, output_dir, env_file, cron)
