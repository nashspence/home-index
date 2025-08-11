from __future__ import annotations

import json
import os
import shutil
from pathlib import Path
from typing import Any, Callable

from features.f2 import duplicate_finder
from shared import compose, search_meili, wait_for


def _run_once(
    compose_file: Path,
    workdir: Path,
    output_dir: Path,
    doc_relpaths: list[str],
    setup_input: Callable[[Path], None] | None = None,
    *,
    override_ids: dict[str, str] | None = None,
    next_map: dict[str, str] | None = None,
    env_file: Path | None = None,
) -> list[str]:
    if output_dir.exists():
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True)
    (output_dir / "modules_config.json").write_text('{"modules": []}')

    input_dir = workdir / "input"
    if input_dir.exists():
        shutil.rmtree(input_dir)
    input_dir.mkdir(parents=True)
    if setup_input:
        setup_input(input_dir)

    metadata_dir = output_dir / "metadata"
    by_id = metadata_dir / "by-id"
    by_path = metadata_dir / "by-path"
    by_id.mkdir(parents=True)
    by_path.mkdir(parents=True)

    doc_ids: list[str] = []
    docs_by_id: dict[str, dict[str, Any]] = {}
    for i, doc_relpath in enumerate(doc_relpaths, start=1):
        doc_path = input_dir / doc_relpath
        if override_ids and doc_relpath in override_ids:
            doc_id = override_ids[doc_relpath]
        elif doc_path.exists():
            doc_id = duplicate_finder.compute_hash(doc_path)
        else:
            doc_id = f"hash{i}"
        doc_ids.append(doc_id)
        doc = docs_by_id.get(doc_id)
        if not doc:
            doc = {
                "id": doc_id,
                "paths": {},
                "paths_list": [],
                "mtime": 1.0,
                "size": 1,
                "type": "text/plain",
                "copies": 0,
                "version": 1,
                "next": "",
            }
            docs_by_id[doc_id] = doc
        doc["paths"][doc_relpath] = 1.0
        doc["paths_list"].append(doc_relpath)
        doc["copies"] = len(doc["paths"])
        if next_map and doc_relpath in next_map:
            doc["next"] = next_map[doc_relpath]

    for doc_id, doc in docs_by_id.items():
        doc_dir = by_id / str(doc_id)
        doc_dir.mkdir(exist_ok=True)
        (doc_dir / "document.json").write_text(json.dumps(doc))
        for relpath in doc["paths_list"]:
            link = by_path / Path(relpath)
            link.parent.mkdir(parents=True, exist_ok=True)
            relative_target = os.path.relpath(by_id / str(doc_id), link.parent)
            if link.is_symlink():
                link.unlink()
            link.symlink_to(relative_target, target_is_directory=True)

    compose(compose_file, workdir, "up", "-d", env_file=env_file)
    by_id_dir = output_dir / "metadata" / "by-id"
    wait_for(
        lambda: by_id_dir.exists() and any(by_id_dir.iterdir()),
        message="metadata",
    )

    for doc_id in doc_ids:
        search_meili(compose_file, workdir, f'id = "{doc_id}"')

    return doc_ids


def _run_sync(
    compose_file: Path,
    workdir: Path,
    output_dir: Path,
    doc_ids: list[str],
    *,
    env_file: Path | None = None,
) -> None:
    compose(compose_file, workdir, "up", "-d", env_file=env_file)
    by_id_dir = output_dir / "metadata" / "by-id"
    wait_for(
        lambda: all((by_id_dir / did).exists() for did in doc_ids),
        message="metadata",
    )
    for doc_id in doc_ids:
        search_meili(compose_file, workdir, f'id = "{doc_id}"')
    compose(
        compose_file,
        workdir,
        "down",
        "--volumes",
        "--rmi",
        "local",
        env_file=env_file,
        check=False,
    )
