from __future__ import annotations

from pathlib import Path

from shared import compose_paths, search_meili

from .helpers import _run_uid_mismatch


def f4s11(tmp_path: Path) -> None:
    compose_file, workdir, output_dir = compose_paths(__file__)
    env_file = tmp_path / ".env"
    doc_id = _run_uid_mismatch(compose_file, workdir, output_dir, env_file)
    docs = search_meili(compose_file, workdir, f'id = "{doc_id}"')
    assert any(doc["id"] == doc_id for doc in docs)
