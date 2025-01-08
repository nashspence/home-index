import logging
import os
import json
from xmlrpc.server import SimpleXMLRPCServer
from contextlib import contextmanager
from pathlib import Path

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s"
)

HOST = os.environ.get("HOST", "0.0.0.0")
PORT = int(os.environ.get("PORT", 9000))
LOGGING_LEVEL = os.environ.get("LOGGING_LEVEL", "INFO")
METADATA_DIRECTORY = Path(os.environ.get("METADATA_DIRECTORY", "/files/metadata"))
FILES_DIRECTORY = Path(os.environ.get("FILES_DIRECTORY", "/files"))
BY_ID_DIRECTORY = Path(
    os.environ.get("BY_ID_DIRECTORY", str(METADATA_DIRECTORY / "by-id"))
)


def file_path_from_meili_doc(document):
    relpath = next(iter(document["paths"].keys()))
    return Path(FILES_DIRECTORY / relpath)


def metadata_dir_path_from_doc(name, document):
    return Path(BY_ID_DIRECTORY / document["id"] / name)


@contextmanager
def log_to_file_and_stdout(file_path):
    file_handler = logging.FileHandler(file_path)
    file_handler.setLevel(LOGGING_LEVEL)
    file_formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")
    file_handler.setFormatter(file_formatter)

    stream_handler = logging.StreamHandler()
    stream_handler.setLevel(LOGGING_LEVEL)
    stream_formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")
    stream_handler.setFormatter(stream_formatter)

    root_logger = logging.getLogger()
    root_logger.addHandler(file_handler)
    root_logger.addHandler(stream_handler)

    try:
        yield
    finally:
        root_logger.removeHandler(file_handler)
        file_handler.close()
        root_logger.removeHandler(stream_handler)


def run_server(name, hello_fn, check_fn, run_fn, load_fn=None, unload_fn=None):
    class Handler:
        def hello(self):
            logging.info("hello")
            return json.dumps(hello_fn())

        def check(self, docs):
            response = set()
            for document in json.loads(docs):
                file_path = file_path_from_meili_doc(document)
                metadata_dir_path = metadata_dir_path_from_doc(name, document)
                with log_to_file_and_stdout(metadata_dir_path / "log.txt"):
                    if check_fn(file_path, document, metadata_dir_path):
                        response.add(document["id"])
            return json.dumps(response)

        def load(self):
            logging.info("load")
            if load_fn:
                load_fn()

        def run(self, document_json):
            document = json.loads(document_json)
            file_path = file_path_from_meili_doc(document)
            metadata_dir_path = metadata_dir_path_from_doc(name, document)
            with log_to_file_and_stdout(metadata_dir_path / "log.txt"):
                x = run_fn(file_path, document, metadata_dir_path)
            return json.dumps(x)

        def unload(self):
            logging.info("unload")
            if unload_fn:
                unload_fn()

    server.register_instance(Handler())
    print(f"Server running at {server.server_address}")
    server.serve_forever()
