from __future__ import annotations

from pathlib import Path
import os

import subprocess
from shared import compose, compose_paths, wait_for

from .helpers import _container_status


def test_f4s12(tmp_path: Path) -> None:
    compose_file, workdir, output_dir = compose_paths(__file__)
    env_file = tmp_path / ".env"
    env_file.write_text(
        f"COMMIT_SHA={os.environ.get('COMMIT_SHA', 'main')}\nEXAMPLE_UID=bad\n"
    )
    compose(compose_file, workdir, "up", "-d", env_file=env_file, check=False)
    try:
        wait_for(
            lambda: _container_status(compose_file, workdir, "example-module")
            == "exited",
            timeout=60,
            message="example-module exit",
        )
        logs = subprocess.check_output(
            [
                "docker",
                "compose",
                "-f",
                str(compose_file),
                "logs",
                "example-module",
            ],
            cwd=workdir,
        ).decode()
        assert "fatal mis-configuration" in logs
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
