import logging
import os
from pathlib import Path
from typing import Any, Mapping

from features.F4.home_index_module import run_server

VERSION = 1
NAME = os.environ.get("NAME", "chunk_module")


def check(
    file_path: Path, document: Mapping[str, Any], metadata_dir_path: Path
) -> bool:
    return True


def run(
    file_path: Path, document: Mapping[str, Any], metadata_dir_path: Path
) -> Mapping[str, Any]:
    logging.info("start %s", file_path)
    text = file_path.read_text()
    doc = dict(document)
    doc[f"{NAME}.content"] = text
    logging.info("done")
    return doc


if __name__ == "__main__":
    run_server(check, run)
