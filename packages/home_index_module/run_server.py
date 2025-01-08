import logging
import os
import json
from xmlrpc.server import SimpleXMLRPCServer
from socketserver import ThreadingMixIn
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


class ThreadedXMLRPCServer(ThreadingMixIn, SimpleXMLRPCServer):
    pass


def run_server(hello_fn, check_fn, run_fn, load_fn=None, unload_fn=None):
    class Handler:
        def hello(self):
            logging.info("hello")
            return json.dump(hello_fn())

        def check(self, file_relpath, document_json, metadata_dir_relpath):
            file_path = FILES_DIRECTORY / file_relpath
            metadata_dir_path = METADATA_DIRECTORY / metadata_dir_relpath
            with log_to_file_and_stdout(metadata_dir_path / "log.txt"):
                x = check_fn(file_path, json.loads(document_json), metadata_dir_path)
            return json.dump(x)

        def load(self):
            logging.info("load")
            if load_fn:
                load_fn()

        def run(self, file_relpath, document_json, metadata_dir_relpath):
            file_path = FILES_DIRECTORY / file_relpath
            metadata_dir_path = METADATA_DIRECTORY / metadata_dir_relpath
            with log_to_file_and_stdout(metadata_dir_path / "log.txt"):
                x = run_fn(file_path, json.loads(document_json), metadata_dir_path)
            return json.dump(x)

        def unload(self):
            logging.info("unload")
            if unload_fn:
                unload_fn()

    server = ThreadedXMLRPCServer((HOST, PORT), allow_none=True)
    server.register_instance(Handler())
    print(f"Threaded server running at {server.server_address}")
    server.serve_forever()
