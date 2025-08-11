import json
import logging
import os
from pathlib import Path
from typing import Any, Mapping

from features.f4.home_index_module import run_server

VERSION = 1
NAME = os.environ.get("NAME", "crash_module")
QUEUE_NAME = os.environ.get("QUEUE_NAME", NAME)


def check(
    file_path: Path, document: Mapping[str, Any], metadata_dir_path: Path
) -> bool:
    return True


def run(
    file_path: Path, document: Mapping[str, Any], metadata_dir_path: Path
) -> Mapping[str, Any]:
    if os.environ.get("CRASH") == "1":
        logging.info("crashing")
        raise RuntimeError("boom")
    (metadata_dir_path / "version.json").write_text(json.dumps({"version": VERSION}))
    return document


if __name__ == "__main__":
    run_server(check, run)
