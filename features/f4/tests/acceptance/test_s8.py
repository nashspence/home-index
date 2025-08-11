from __future__ import annotations

from pathlib import Path

from shared import compose_paths

from .helpers import _run_timeout


def test_f4s8(tmp_path: Path) -> None:
    compose_file, workdir, output_dir = compose_paths(__file__)
    env_file = tmp_path / ".env"
    _run_timeout(compose_file, workdir, output_dir, env_file)
