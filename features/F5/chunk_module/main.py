import json
import logging
import os
from pathlib import Path
from typing import Any, Mapping

from features.F4.home_index_module import run_server

VERSION = 1
# default the module name to QUEUE_NAME so returned metadata matches the
# queue configured in docker-compose
NAME = os.environ.get("NAME") or os.environ.get("QUEUE_NAME", "chunk_module")


def check(
    file_path: Path, document: Mapping[str, Any], metadata_dir_path: Path
) -> bool:
    """Return ``True`` if ``file_path`` should be processed."""

    content_path = metadata_dir_path / "content.json"
    if content_path.exists():
        try:
            with content_path.open() as fh:
                data = json.load(fh)
            if data == file_path.read_text():
                return False
        except Exception:
            pass
    return True


def run(
    file_path: Path, document: Mapping[str, Any], metadata_dir_path: Path
) -> Mapping[str, Any] | dict[str, Any]:
    logging.info("start %s", file_path)
    text = file_path.read_text()
    doc = dict(document)
    logging.info("done")
    return {"document": doc, "content": text}


if __name__ == "__main__":
    run_server(check, run)
