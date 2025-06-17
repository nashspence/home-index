# Home Index

Home Index is a file indexing service built around [Meilisearch](https://www.meilisearch.com/). It scans a directory of files, stores metadata under a configurable location and can enrich that metadata by calling external **modules**. Modules handle tasks such as transcription, OCR, scraping, thumbnails or caption generation so your files become easily searchable.

This project requires **Python 3.8 or higher** when running outside the provided Docker environment.

## Quick start

The repository includes a `docker-compose.yml` that starts Home Index, Meilisearch and a sample module. After installing Docker, run:

```bash
docker compose up
```

Files and logs are stored under `bind-mounts/`. Edit the compose file to adjust any paths or environment variables.

## Features

The list below highlights key functionality. Each tested feature links directly to its verifying integration test.

- [**File Documents Match The Expected Schema**](tests/test_meilisearch_schema.py#L9-L12) — file documents match the expected schema
- [**Chunk Documents Follow The Chunk Schema**](tests/test_meilisearch_file_chunk_schema.py#L7-L9) — chunk documents follow the chunk schema
- [**Modules Communicate Via XML-RPC**](tests/test_run_server_module.py#L31-L66) — modules communicate via XML-RPC
- [**Modules Can Add And Remove Chunk Data**](tests/test_chunk_integration.py#L140-L200) — modules can add and remove chunk data
- [**Modules May Return Only Updated Documents**](tests/test_chunk_integration.py#L203-L251) — modules may return only updated documents
- [**Retry Helper Stops When A Call Succeeds**](tests/test_retry.py#L10-L28) — retry helper stops when a call succeeds
- [**Retry Helper Fails After Repeated Errors**](tests/test_retry.py#L31-L44) — retry helper fails after repeated errors
- [**Indexing Runs Across Many Files And Modules**](tests/test_large_indexing.py#L103-L168) — indexing runs across many files and modules
- [**Cron Schedules Are Parsed From The Environment**](tests/test_schedule.py#L8-L24) — cron schedules are parsed from the environment
- [**Malformed Cron Expressions Raise ValueError**](tests/test_schedule.py#L27-L37) — malformed cron expressions raise ValueError
- [**Text Embeddings Use SentenceTransformer Models**](tests/test_embeddings.py#L19-L34) — text embeddings use SentenceTransformer models
- [**Metadata Persists If The Archive Directory Is Temporarily Missing**](tests/test_archive_support.py#L10-L48) — metadata persists if the archive directory is temporarily missing
- [**Module Migrations Persist Version Upgrades**](tests/test_module_migrations.py#L7-L28) — module migrations persist version upgrades
- [**Scheduler Attaches A CronTrigger Job For Periodic Indexing**](tests/test_schedule.py#L40-L85) — scheduler attaches a CronTrigger job for periodic indexing
- [**Metadata And Symlinks Are Purged After An Archive File Is Removed**](tests/test_archive_support.py#L51-L91) — metadata and symlinks are purged after an archive file is removed
- [**TokenTextSplitter Divides Chunk Text Into Smaller Documents**](tests/test_chunk_utils.py#L23-L64) — token text splitter divides chunk text into smaller documents
- [**Segments With Headers Convert To Chunk Documents Referencing The Source File**](tests/test_chunk_utils.py#L7-L20) — segments with headers convert to chunk documents referencing the source file

## Running manually

You can also run the service directly with Python:

```bash
pip install -r requirements.txt
python -m home_index.main
```

Before launching, set the required environment variables described below.

## Configuration

Key environment variables (defaults in brackets):

- `MEILISEARCH_HOST` – address of Meilisearch [`http://localhost:7700`]
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

## Development Philosophy

Home Index favors pragmatic integration tests over unit tests. Every feature is
tested end-to-end using the same Docker configuration that powers development
and release builds. Local test runs are optional for debugging—CI is the source
of truth. New functionality should be delivered in small, atomic PRs with clear
integration tests and minimal mocking. macOS-only features use a dedicated
`runs-on: macos-latest` workflow.

## Purpose

Home Index makes directories of files searchable with minimal configuration. It stores file metadata in Meilisearch and lets modules contribute information such as extracted text or image thumbnails. This combination enables rich search and retrieval over personal data.

## License

Distributed under the MIT License. See [LICENSE](LICENSE) for details.
