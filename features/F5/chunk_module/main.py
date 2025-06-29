import logging
import os
from pathlib import Path
from typing import Any, Dict, Mapping
import json

from features.F4.home_index_module import (
    run_server,
    segments_to_chunk_docs,
    split_chunk_docs,
)

VERSION = 1
NAME = os.environ.get("NAME", "chunk_module")


def hello() -> Dict[str, Any]:
    return {
        "name": NAME,
        "version": VERSION,
        "filterable_attributes": [],
        "sortable_attributes": [],
    }


def check(
    file_path: Path, document: Mapping[str, Any], metadata_dir_path: Path
) -> bool:
    return True


def run(
    file_path: Path, document: Mapping[str, Any], metadata_dir_path: Path
) -> Mapping[str, Any]:
    logging.info("start %s", file_path)
    text = file_path.read_text()

    # Build one segment from the entire file then convert to chunk documents.
    segments = [{"doc": {"text": text}}]
    chunk_docs = segments_to_chunk_docs(segments, document["id"], module_name=NAME)

    # Split chunk documents by tokens to avoid oversize passages.
    chunk_docs = split_chunk_docs(chunk_docs)

    for chunk in chunk_docs:
        (metadata_dir_path / f"{chunk['id']}.json").write_text(
            json.dumps(chunk, indent=4)
        )

    logging.info("done")
    return {"document": document, "chunk_docs": chunk_docs}


if __name__ == "__main__":
    run_server(NAME, hello, check, run)
