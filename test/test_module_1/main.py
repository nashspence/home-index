# region "debugpy"


import os
import debugpy

debugpy.listen(("0.0.0.0", 5678))

if str(os.environ.get("WAIT_FOR_DEBUG_CLIENT", "false")).lower() == "true":
    print("Waiting for debugger to attach...")
    debugpy.wait_for_client()
    print("Debugger attached.")
    debugpy.breakpoint()


# endregion
# region "import"


import json
import logging
from home_index_module import run_server


# endregion
# region "config"

VERSION = 1
NAME = os.environ.get("NAME", "test_module_1")


# endregion
# region "hello"


def hello():
    return {
        "name": NAME,
        "version": 1,
        "filterable_attributes": [],
        "sortable_attributes": [],
    }


# endregion
# region "check/run"


def check(file_path, document, metadata_dir_path):
    return True


def run(file_path, document, metadata_dir_path):
    global logging
    logging.info(f"start {file_path}")
    version_path = metadata_dir_path / f"version.json"
    with open(version_path, "w") as file:
        json.dump({"version": VERSION}, file, indent=4)
    logging.info("done")
    return document


# endregion

if __name__ == "__main__":
    run_server(hello, check, run)
