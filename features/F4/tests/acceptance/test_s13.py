from __future__ import annotations

from pathlib import Path

from shared import compose_paths

from .helpers import _run_crash_isolation


def f4s13(tmp_path: Path) -> None:
    compose_file, workdir, output_dir = compose_paths(__file__)
    env_file = tmp_path / ".env"
    doc_id, logs = _run_crash_isolation(compose_file, workdir, output_dir, env_file)
    version_file = (
        output_dir / "metadata" / "by-id" / doc_id / "example-module" / "version.json"
    )
    assert version_file.exists()
    assert "crashing" in logs
