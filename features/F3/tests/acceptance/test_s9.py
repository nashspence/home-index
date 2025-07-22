from __future__ import annotations

from pathlib import Path

from shared import compose, compose_paths, dump_logs, search_meili

from .helpers import _run_once


def f3s9(tmp_path: Path) -> None:
    compose_file, workdir, output_dir = compose_paths(__file__)

    def setup(input_dir: Path) -> None:
        drive1 = input_dir / "archive" / "drive1"
        drive1.mkdir(parents=True)
        (drive1 / "a.txt").write_text("a")
        archive = input_dir / "archive"
        (archive / "drive2-status-ready").write_text("old")

    try:
        ids = _run_once(
            compose_file,
            workdir,
            output_dir,
            ["archive/drive1/a.txt", "archive/drive2/b.txt"],
            setup,
            override_ids={"archive/drive2/b.txt": "hash2"},
        )
        id1 = ids[0]
        id2 = "hash2"
        ready1 = workdir / "input" / "archive" / "drive1-status-ready"
        ready2 = workdir / "input" / "archive" / "drive2-status-ready"
        assert ready1.exists()
        assert ready2.read_text() == "old"
        docs1 = search_meili(compose_file, workdir, f'id = "{id1}"')
        docs2 = search_meili(compose_file, workdir, f'id = "{id2}"')
        assert all(not doc["offline"] for doc in docs1)
        assert all(doc["offline"] for doc in docs2)
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
