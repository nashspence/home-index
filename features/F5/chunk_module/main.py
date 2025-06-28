import logging
import os
from pathlib import Path
from typing import Any, Dict, Mapping
import json

from features.F4.home_index_module import run_server

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
    text = Path(file_path).read_text()
    chunk = {
        "id": f"{NAME}_{document['id']}_0",
        "file_id": document["id"],
        "module": NAME,
        "text": text,
    }
    (metadata_dir_path / f"{chunk['id']}.json").write_text(json.dumps(chunk, indent=4))
    logging.info("done")
    return {"document": document, "chunk_docs": [chunk]}


if __name__ == "__main__":
    run_server(NAME, hello, check, run)
