from __future__ import annotations

from pathlib import Path

from shared import compose_paths, search_meili

from .helpers import _run_once, _get_doc_id, _run_add_module


def f4s7(tmp_path: Path) -> None:
    compose_file, workdir, output_dir = compose_paths(__file__)
    env_file = tmp_path / ".env"
    _run_once(compose_file, workdir, output_dir, env_file)
    doc_id = _get_doc_id(workdir, output_dir)
    docs = search_meili(compose_file, workdir, f'id = "{doc_id}"')
    assert any(doc["id"] == doc_id for doc in docs)
    _run_add_module(compose_file, workdir, output_dir, env_file)
    docs_after = search_meili(compose_file, workdir, f'id = "{doc_id}"')
    assert any(doc["id"] == doc_id for doc in docs_after)
