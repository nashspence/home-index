# Home Index

Home Index is a small file indexing service built around [Meilisearch](https://www.meilisearch.com/).
It scans a directory of files, stores metadata under `METADATA_DIRECTORY` and
periodically enriches that metadata by calling external modules via XML‑RPC.

Modules can handle tasks such as transcription, OCR, scraping, thumbnails or
caption generation. Example modules can be found in these repositories:

- [home-index-transcribe](https://github.com/nashspence/home-index-transcribe)
- [home-index-read](https://github.com/nashspence/home-index-read)
- [home-index-scrape](https://github.com/nashspence/home-index-scrape)
- [home-index-thumbnail](https://github.com/nashspence/home-index-thumbnail)
- [home-index-caption](https://github.com/nashspence/home-index-caption)

A minimal test module lives under `test/test_module_1`.

## Running with Docker Compose

The project includes a `docker-compose.yml` demonstrating how to run the indexer,
Meilisearch and a sample module. Key settings are provided via environment
variables:

```yaml
services:
  home-index:
    build:
      context: .
      dockerfile: Dockerfile
    container_name: home-index
    depends_on:
      - meilisearch
      - home-index-test-module-1
    environment:
      - DEBUG=True
      - MEILISEARCH_HOST=http://meilisearch:7700
      - MODULES=http://home-index-test-module-1:9000
      - TZ=America/Los_Angeles
      - WAIT_FOR_DEBUGPY_CLIENT=True
    ports:
      - '5678:5678' # debugpy
    restart: unless-stopped
    volumes:
      - ./bind-mounts/home-index:/home-index
      - ./bind-mounts/files:/files
```

Volumes under `bind-mounts` hold the indexed files and any logs.

## Environment variables

Most behaviour is configured by environment variables. Important ones are shown
below (defaults in brackets):

- `MEILISEARCH_HOST` – address of Meilisearch [`http://localhost:7700`]
- `MEILISEARCH_INDEX_NAME` – index name [`files`]
- `INDEX_DIRECTORY` – root of files to index [`/files`]
- `METADATA_DIRECTORY` – where metadata is stored [`/files/metadata`]
- `MODULES` – comma-separated list of module RPC endpoints
- `MODULES_MAX_SECONDS` – maximum seconds to run a module pass
- `MODULES_SLEEP_SECONDS` – wait time between module passes
- `CRON_EXPRESSION` – when to sync files when not in debug mode (`0 3 * * *`)

The code defines many more variables (see `packages/home_index/main.py`). The
section configuring them looks like:

```python
DEBUG = str(os.environ.get("DEBUG", "False")) == "True"

MODULES_MAX_SECONDS = int(
    os.environ.get(
        "MODULES_MAX_SECONDS",
        5 if DEBUG else 300,
    )
)
MODULES_SLEEP_SECONDS = int(
    os.environ.get(
        "MODULES_SLEEP_SECONDS",
        os.environ.get(
            "MODULES_MAX_SECONDS",
            1 if DEBUG else 1800,
        ),
    )
)

MEILISEARCH_BATCH_SIZE = int(os.environ.get("MEILISEARCH_BATCH_SIZE", "10000"))
MEILISEARCH_HOST = os.environ.get("MEILISEARCH_HOST", "http://localhost:7700")
MEILISEARCH_INDEX_NAME = os.environ.get("MEILISEARCH_INDEX_NAME", "files")

CPU_COUNT = os.cpu_count()
MAX_HASH_WORKERS = int(os.environ.get("MAX_HASH_WORKERS", CPU_COUNT / 2))
MAX_FILE_WORKERS = int(os.environ.get("MAX_FILE_WORKERS", CPU_COUNT / 2))
```

## Module interface

Modules are simple XML‑RPC servers. The helper
`home_index_module.run_server` exposes the required RPC methods:

```python
def run_server(name, hello_fn, check_fn, run_fn, load_fn=None, unload_fn=None):
    class Handler:
        def hello(self):
            logging.info("hello")
            return json.dumps(hello_fn())

        def check(self, docs):
            response = set()
            for document in json.loads(docs):
                file_path = file_path_from_meili_doc(document)
                try:
                    metadata_dir_path = metadata_dir_path_from_doc(name, document)
                    with log_to_file_and_stdout(metadata_dir_path / "log.txt"):
                        if check_fn(file_path, document, metadata_dir_path):
                            response.add(document["id"])
                except Exception as e:
                    logging.exception(f'failed to check "{file_path}"')
            return json.dumps(list(response))

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
    server = SimpleXMLRPCServer((HOST, PORT), allow_none=True)
    server.register_instance(Handler())
    print(f"Server running at {server.server_address}")
```

Each module must implement `hello`, `check`, `run`, and optionally
`load`/`unload`. `hello` returns metadata (name, version, filterable and sortable
attributes). `check` receives candidate documents and returns which ones to
process. `run` performs the work and may store data in the provided metadata
folder. The value returned from `run` may be a single document or a list of
documents. File metadata documents carry `doc_type="file"` while documents
created by modules default to `doc_type="content"`.

## Development

Install the requirements and run the tests:

```bash
pip install -r requirements.txt
pytest -q
```

The `setup.py` package metadata is minimal:

```python
from setuptools import setup, find_packages

setup(
    name="home_index",
    version="1.0.0",
    description="A package for running the home-index server.",
    author="Nash Spence",
    author_email="nashspence@gmail.com",
    url="https://github.com/nashspence/home-index",
    packages=find_packages(where="packages"),
    package_dir={"": "packages"},
)
```

## License

No license information is provided. See the repository history for details.
