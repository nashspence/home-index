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

The list below highlights key functionality. Each tested feature links directly
to its verifying test case.

- `test_schema_is_valid` – file documents match the expected schema – [tests/test_meilisearch_schema.py](tests/test_meilisearch_schema.py)
- `test_chunk_schema_is_valid` – chunk documents follow the chunk schema – [tests/test_meilisearch_file_chunk_schema.py](tests/test_meilisearch_file_chunk_schema.py)
- `test_run_server_basic` – modules communicate via XML‑RPC – [tests/test_run_server_module.py](tests/test_run_server_module.py)
- `test_run_module_adds_and_deletes_chunks` – modules can add and remove chunk data – [tests/test_chunk_integration.py](tests/test_chunk_integration.py)
- `test_run_module_handles_document_return` – modules may return only updated documents – [tests/test_chunk_integration.py](tests/test_chunk_integration.py)
- `test_retry_until_ready_success` – retry helper stops when a call succeeds – [tests/test_retry.py](tests/test_retry.py)
- `test_retry_until_ready_failure` – retry helper fails after repeated errors – [tests/test_retry.py](tests/test_retry.py)
- `test_sync_and_run_many_files` – indexing runs across many files and modules – [tests/test_large_indexing.py](tests/test_large_indexing.py)
- `test_parse_cron_env_parses_expression` – cron schedules are parsed from the environment – [tests/test_schedule.py](tests/test_schedule.py)
- `test_embed_texts_produces_vectors` – text embeddings use SentenceTransformer models – [tests/test_embeddings.py](tests/test_embeddings.py)
- `test_archive_sync_retains_unmounted_docs` – metadata for offline archive files is retained – [tests/test_archive_support.py](tests/test_archive_support.py)
- `test_apply_migrations_if_needed` – module migrations persist version upgrades – [tests/test_module_migrations.py](tests/test_module_migrations.py)

Untested features:

- Cron-based indexing run via APScheduler
- Archive directory cleanup when files are permanently removed

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

## Purpose

Home Index makes directories of files searchable with minimal configuration. It stores file metadata in Meilisearch and lets modules contribute information such as extracted text or image thumbnails. This combination enables rich search and retrieval over personal data.

## License

Distributed under the MIT License. See [LICENSE](LICENSE) for details.
