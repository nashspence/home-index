state = {"loaded": False, "unloaded": False}

NAME = "pretend"
VERSION = 1


def hello():
    return {
        "name": NAME,
        "version": VERSION,
        "filterable_attributes": [],
        "sortable_attributes": [],
    }


def check(file_path, document, metadata_dir_path):
    return True


def run(file_path, document, metadata_dir_path):
    chunk = {
        "id": "example_chunk",
        "file_id": document["id"],
        "module": NAME,
        "text": "sample text",
    }
    return {"document": document, "chunk_docs": [chunk]}


def load():
    state["loaded"] = True


def unload():
    state["unloaded"] = True


def start(port):
    import os
    import importlib

    os.environ["PORT"] = str(port)
    rs = importlib.import_module("features.F4.home_index_module.run_server")
    rs = importlib.reload(rs)
    rs.run_server(NAME, hello, check, run, load_fn=load, unload_fn=unload)
