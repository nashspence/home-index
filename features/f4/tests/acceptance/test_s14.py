from __future__ import annotations

from pathlib import Path
import tempfile

from shared import compose_paths

from .helpers import _run_share_group_rotation


def test_f4s14() -> None:
    compose_file, workdir, output_dir = compose_paths(__file__)
    env_file = Path(tempfile.mkdtemp()) / ".env"
    logs_example, logs_timeout = _run_share_group_rotation(
        compose_file, workdir, output_dir, env_file
    )
    example_start = next(
        (idx for idx, line in enumerate(logs_example.splitlines()) if "start" in line),
        -1,
    )
    timeout_start = next(
        (idx for idx, line in enumerate(logs_timeout.splitlines()) if "start" in line),
        -1,
    )
    assert example_start != -1 and timeout_start != -1
    assert example_start < timeout_start
