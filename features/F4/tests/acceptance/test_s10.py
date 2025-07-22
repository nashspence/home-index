from __future__ import annotations

from pathlib import Path
import tempfile

from shared import compose_paths

from .helpers import _run_once, _get_doc_id, _run_again


def f4s10() -> None:
    compose_file, workdir, output_dir = compose_paths(__file__)
    env_file = Path(tempfile.mkdtemp()) / ".env"
    _run_once(compose_file, workdir, output_dir, env_file)
    doc_id = _get_doc_id(workdir, output_dir)
    version_file = (
        output_dir / "metadata" / "by-id" / doc_id / "example-module" / "version.json"
    )
    mtime = version_file.stat().st_mtime
    _run_again(compose_file, workdir, output_dir, env_file)
    assert version_file.stat().st_mtime == mtime
