import json
import logging
import os

from features.F4.home_index_module import run_server

VERSION = 1
NAME = os.environ.get("NAME", "example_module")


def hello():
    """Return metadata describing the module."""
    return {
        "name": NAME,
        "version": VERSION,
        "filterable_attributes": [],
        "sortable_attributes": [],
    }


def check(file_path, document, metadata_dir_path):
    """Return True if the document should be processed."""
    version_path = metadata_dir_path / "version.json"
    if not version_path.exists():
        return True
    with open(version_path) as file:
        version = json.load(file)
    return version["version"] != VERSION


def run(file_path, document, metadata_dir_path):
    """Process a document and return the updated version."""
    logging.info("start %s", file_path)
    version_path = metadata_dir_path / "version.json"
    with open(version_path, "w") as file:
        json.dump({"version": VERSION}, file, indent=4)
    logging.info("done")
    return document


if __name__ == "__main__":
    run_server(NAME, hello, check, run)
