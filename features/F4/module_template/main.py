import json
import logging
import os
from pathlib import Path
from typing import Any, Dict, Mapping, cast

from features.F4.home_index_module import run_server

VERSION = 1
NAME = os.environ.get("NAME", "example_module")
COMMIT_SHA = os.environ.get("COMMIT_SHA", "main")


def hello() -> Dict[str, Any]:
    """Return metadata describing the module."""
    return {
        "name": NAME,
        "version": VERSION,
        "target": COMMIT_SHA,
        "filterable_attributes": [],
        "sortable_attributes": [],
    }


def check(
    file_path: Path, document: Mapping[str, Any], metadata_dir_path: Path
) -> bool:
    """Return True if the document should be processed."""
    version_path = metadata_dir_path / "version.json"
    if not version_path.exists():
        return True
    with open(version_path) as file:
        version = cast(Dict[str, Any], json.load(file))
    return int(version["version"]) != VERSION


def run(
    file_path: Path, document: Mapping[str, Any], metadata_dir_path: Path
) -> Mapping[str, Any]:
    """Process a document and return the updated version."""
    logging.info("start %s", file_path)
    version_path = metadata_dir_path / "version.json"
    with open(version_path, "w") as file:
        json.dump({"version": VERSION}, file, indent=4)
    logging.info("done")
    return document


if __name__ == "__main__":
    run_server(NAME, hello, check, run)
