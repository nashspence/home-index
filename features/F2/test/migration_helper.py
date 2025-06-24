from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any, Callable


def simulate_v0_and_rerun(
    compose_file: Path,
    workdir: Path,
    output_dir: Path,
    run_again: Callable[
        [Path, Path, Path],
        tuple[Path, Path, list[dict[str, Any]], list[dict[str, Any]]],
    ],
) -> tuple[Path, Path, list[dict[str, Any]], list[dict[str, Any]]]:
    """Downgrade docs to schema v0, rerun the container, and confirm migration."""
    by_id_dir = output_dir / "metadata" / "by-id"
    subprocess.run(
        [
            "docker",
            "compose",
            "-f",
            str(compose_file),
            "stop",
        ],
        check=True,
        cwd=workdir,
    )
    for doc_dir in by_id_dir.iterdir():
        if not doc_dir.is_dir():
            continue
        doc_path = doc_dir / "document.json"
        data = json.loads(doc_path.read_text())
        data.pop("paths_list", None)
        data.pop("version", None)
        doc_path.write_text(json.dumps(data))

    by_id_dir, by_path_dir, dup_docs, unique_docs = run_again(
        compose_file, workdir, output_dir
    )

    for doc_dir in by_id_dir.iterdir():
        doc = json.loads((doc_dir / "document.json").read_text())
        assert "paths_list" in doc and "version" in doc

    return by_id_dir, by_path_dir, dup_docs, unique_docs
