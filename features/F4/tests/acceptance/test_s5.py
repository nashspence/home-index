from __future__ import annotations

from pathlib import Path
import tempfile

from shared import compose_paths, search_meili

from .helpers import _run_once
import pytest


def f4s5() -> None:
    compose_file, workdir, output_dir = compose_paths(__file__)
    (workdir / "input" / "Foo-status-ready").write_text("x")
    env_file = Path(tempfile.mkdtemp()) / ".env"
    _run_once(compose_file, workdir, output_dir, env_file)
    with pytest.raises(AssertionError):
        search_meili(
            compose_file, workdir, 'paths_list = "Foo-status-ready"', timeout=5
        )
