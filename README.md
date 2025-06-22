# Home Index

Home Index is a file indexing service built around [Meilisearch](https://www.meilisearch.com/). It scans a directory of files, stores metadata under a configurable location and can enrich that metadata by calling external **modules**. Modules handle tasks such as transcription, OCR, scraping, thumbnails or caption generation so your files become easily searchable.

This project requires **Python 3.8 or higher** when running outside the provided Docker environment.

## Who

Home Index suits data hoarders and personal archivists wanting a fast search layer for personal files.

## Quick start

The repository includes a `docker-compose.yml` that starts Home Index, Meilisearch and a sample module. After installing Docker, run:

```bash
docker compose up
```

Files and logs are stored under `bind-mounts/`. Edit the compose file to adjust any paths or environment variables.

## Features

These goals define the features of this application, and will be referenced
everywhere else by their number.

### F1: my home server to be available when I need it

Home Index stays available by periodically synchronizing its index with your
files. The scheduler for this behavior lives under `features/F1`. The refresh
schedule is controlled by the `CRON_EXPRESSION` environment variable. Automated
tests start the service in Docker and confirm the scheduler runs on this
interval.

### F2: to link to my files by path

Every indexed document records all of its file paths in the `metadata/by-path`
directory. This allows you to move or rename files while keeping historical
references intact.

### F3: to know my files that were last modified within a range of time

Modification timestamps are indexed so you can filter documents by date.

### F4: to know my files of a specific type

MIME types are detected and stored for each file, enabling type-based queries.

### F5: to know my largest files

File sizes are stored in the index which allows sorting or filtering by size.

### F6: to know my duplicates files

File hashes are computed so duplicates can be detected across directories.

### F7: to know about my files even when they are on disconnected external media

An archive directory preserves metadata for files moved to removable media so
search results remain available.

### F8: to know other information about my files

External modules can attach additional metadata such as OCR text or captions.

### F9: to view my files in a web browser

Optional front-end applications integrate with Meilisearch to provide a web UI.

### F10: to know which ones of my files match a concept

Embeddings allow semantic queries against stored vectors.

### F11: to know which ones of my files contain a text phrase

Full text search through Meilisearch locates matching documents.

### F12: to separate my manually created files from my derived files

Metadata marks derived files so they can be filtered from manually created ones.

## Running manually

You can also run the service directly with Python:

```bash
pip install -r requirements.txt
python -m home_index.main
```

Before launching, set the required environment variables described below.

## Configuration

Key environment variables (defaults in brackets):

- `MEILISEARCH_HOST` – address of Meilisearch [`http://meilisearch:7700`]
- `INDEX_DIRECTORY` – directory containing files to index [`/files`]
- `METADATA_DIRECTORY` – where module output is stored [`/files/metadata`]
- `ARCHIVE_DIRECTORY` – special folder for archived files [`<INDEX_DIRECTORY>/archive`]
- `MODULES` – comma-separated list of module XML‑RPC endpoints
- `CRON_EXPRESSION` – cron expression controlling how often the index is refreshed [`0 3 * * *`]

Additional options can be found in `packages/home_index/main.py`.

## Archive directory

Files placed in the archive directory can be stored on removable media without
being removed from the index. When crawling the index directory Home Index keeps
metadata for any document whose paths are inside `ARCHIVE_DIRECTORY` even if the
physical files are missing. Once the archive media is mounted again the files
are processed like normal, allowing long term storage while preserving search
results.

## Modules

Modules extend Home Index by providing extra metadata. A module is an XML‑RPC server exposing these calls:

- **hello** – return module metadata (name, version, filterable/sortable attributes)
- **check** – given candidate documents, return the IDs of files to process
- **run** – perform work on a document and optionally return chunk documents
- **load** / **unload** *(optional)* – setup or teardown logic

Use `home_index_module.run_server` to expose these functions. See `examples/module_template` for a minimal starting point and `docs/rpc_module_spec.md` for the full RPC specification. Once your module is running, add its endpoint to the `MODULES` environment variable, e.g.:

```bash
MODULES=http://my-module:9000
```

Home Index will automatically call your module to enrich documents.

Modules are called sequentially in the order specified by `MODULES`. Each module is given a limited time slice configured via `MODULES_MAX_SECONDS`. Processing of an individual file is never interrupted once it begins.

### Well-known modules

A few maintained modules provide common functionality out of the box:

- [home-index-read](https://github.com/nashspence/home-index-read) – perform OCR on images and PDFs using EasyOCR.
- [home-index-scrape](https://github.com/nashspence/home-index-scrape) – extract metadata with tools like ExifTool and Apache Tika.
- [home-index-caption](https://github.com/nashspence/home-index-caption) – generate image and video captions using the BLIP model.
- [home-index-transcribe](https://github.com/nashspence/home-index-transcribe) – create transcripts from media with WhisperX.
- [home-index-thumbnail](https://github.com/nashspence/home-index-thumbnail) – produce WebP thumbnails and previews.

## Front-end interfaces

An optional user interface for interacting with your indexed content is
[home-index-rag-query](https://github.com/nashspence/home-index-rag-query). It
offers a Streamlit-driven RAG experience, letting you ask questions against
your files using a locally run language model backed by Meilisearch.

## Purpose

Home Index makes directories of files searchable with minimal configuration. It stores file metadata in Meilisearch and lets modules contribute information such as extracted text or image thumbnails. This combination enables rich search and retrieval over personal data.

## Contributions

Pull requests are welcome. Use the dev container (`.devcontainer/`) via VS Code Remote – Containers to mirror CI. GitHub Actions run integration tests on every push.
The default dev container builds without GPU support. To enable NVIDIA GPUs run with the additional compose file:

```bash
docker compose \
  -f .devcontainer/docker-compose.yml \
  -f .devcontainer/docker-compose.gpu.yml \
  up --build -d
```

## Incremental Adoption

Home Index is gradually aligning with the rules in `AGENTS.md`.

- **F1** is implemented with unit and acceptance tests. **F2–F12** remain
  documentation-only.
- `.devcontainer/` matches the prescribed layout and runs in CI via
  `.github/workflows/test.yml`.
- The release workflow builds and publishes the Docker image using
  `docker/metadata-action` and `docker/build-push-action`.
- CI installs docker-compose so the dev container launches successfully.
- Root `Dockerfile` and `docker-compose.yml` define the runtime environment.
- `agents-check.sh` enforces formatting with Black and Ruff.
- `postStart.sh` (invoked via `docker exec … ./postStart.sh`) sets up the dev environment and runs correctly in CI.
- CI sources the virtual environment before running acceptance tests.
- The dev container now has `/workspace` as its working directory so CI commands run as documented.

## License

Distributed under the MIT License. See [LICENSE](LICENSE) for details.
