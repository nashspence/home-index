from __future__ import annotations

from pathlib import Path

from shared import compose_paths, search_meili, search_chunks

from .helpers import _run_once, _get_doc_id


def test_f4s15(tmp_path: Path) -> None:
    compose_file, workdir, output_dir = compose_paths(__file__)
    env_file = tmp_path / ".env"
    _run_once(compose_file, workdir, output_dir, env_file)
    doc_id = _get_doc_id(workdir, output_dir)
    docs = search_meili(compose_file, workdir, f'id = "{doc_id}"')
    assert any(doc.get("note") == "hello" for doc in docs)
    chunks = search_chunks("hello", filter_expr=f'file_id = "{doc_id}"')
    assert any(chunk["file_id"] == doc_id for chunk in chunks)
