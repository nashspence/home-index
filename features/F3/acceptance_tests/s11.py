from __future__ import annotations

from pathlib import Path
import pytest

from shared import compose, compose_paths, dump_logs, search_meili

from .helpers import _run_once


def f3s11(tmp_path: Path) -> None:
    compose_file, workdir, output_dir = compose_paths(__file__)

    def setup(input_dir: Path) -> None:
        archive = input_dir / "archive"
        archive.mkdir()
        (archive / "Foo-status-ready").write_text("x")

    try:
        _run_once(compose_file, workdir, output_dir, [], setup)
        with pytest.raises(AssertionError):
            search_meili(
                compose_file,
                workdir,
                'paths_list = "archive/Foo-status-ready"',
                timeout=5,
            )
    except Exception:
        dump_logs(compose_file, workdir)
        raise
    finally:
        compose(
            compose_file,
            workdir,
            "down",
            "--volumes",
            "--rmi",
            "local",
            check=False,
        )
