from __future__ import annotations

import shutil
import os
from pathlib import Path
from typing import Any

from features.F2 import duplicate_finder
from shared import compose, search_meili, wait_for


# Ensure local searches use the test Meilisearch instance
os.environ.setdefault("MEILISEARCH_HOST", "http://localhost:7700")


def _prepare_env(workdir: Path, output_dir: Path) -> Path:
    if output_dir.exists():
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True)
    (output_dir / "modules_config.json").write_text('{"modules": []}')

    input_dir = workdir / "input"
    if input_dir.exists():
        shutil.rmtree(input_dir)
    shutil.copytree(Path(__file__).with_name("input"), input_dir)
    return input_dir


def _stat_info(path: Path) -> tuple[int, float, str]:
    stat = path.stat()
    return (
        stat.st_size,
        duplicate_finder.truncate_mtime(stat.st_mtime),
        duplicate_finder.compute_hash(path),
    )


def _run_once(
    compose_file: Path,
    workdir: Path,
    output_dir: Path,
) -> tuple[
    Path,
    Path,
    dict[str, tuple[int, float, str]],
    list[dict[str, Any]],
    list[dict[str, Any]],
]:
    input_dir = _prepare_env(workdir, output_dir)
    info = {name: _stat_info(input_dir / name) for name in ["a.txt", "b.txt", "c.txt"]}
    compose(compose_file, workdir, "up", "-d")
    by_id_dir = output_dir / "metadata" / "by-id"
    wait_for(
        lambda: by_id_dir.exists() and any(by_id_dir.iterdir()), message="metadata"
    )
    by_path_dir = output_dir / "metadata" / "by-path"
    dup_docs = search_meili(compose_file, workdir, "copies = 2")
    uniq_docs = search_meili(compose_file, workdir, "copies = 1")
    assert len(dup_docs) == 1
    assert len(uniq_docs) == 1
    return by_id_dir, by_path_dir, info, dup_docs, uniq_docs


def _sync(compose_file: Path, workdir: Path, output_dir: Path) -> None:
    compose(compose_file, workdir, "up", "-d")
    by_id_dir = output_dir / "metadata" / "by-id"
    wait_for(
        lambda: by_id_dir.exists() and any(by_id_dir.iterdir()), message="metadata"
    )
