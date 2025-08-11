from __future__ import annotations

from pathlib import Path
import tempfile

from shared import compose_paths

from .helpers import _run_once, _get_doc_id, _run_add_module


def test_f4s4() -> None:
    compose_file, workdir, output_dir = compose_paths(__file__)
    env_path = Path(tempfile.mkdtemp()) / ".env"
    _run_once(compose_file, workdir, output_dir, env_path)
    doc_id = _get_doc_id(workdir, output_dir)
    example_version = (
        output_dir / "metadata" / "by-id" / doc_id / "example-module" / "version.json"
    )
    mtime = example_version.stat().st_mtime
    _run_add_module(compose_file, workdir, output_dir, env_path)
    assert example_version.stat().st_mtime == mtime
    timeout_version = (
        output_dir / "metadata" / "by-id" / doc_id / "timeout-module" / "version.json"
    )
    assert timeout_version.exists()
