# Queued Module Specification

Home Index modules extend the indexer with specialised processors such as caption generators, OCR engines or metadata extractors.  Modules run as small services that communicate solely through Redis lists and write their results under each file's metadata directory.

## Environment variables

Every module container must define these variables:

- `QUEUE_NAME` – unique name for the module.
- `REDIS_HOST` – Redis connection string like `http://redis:6379`.
- `TIMEOUT` – seconds a task may run before being requeued. When the limit is reached the job's output is discarded and the file is queued again.
- `WORKER_ID` – unique identifier when using shared resources.
- `RESOURCE_SHARES` – optional YAML describing resource share groups.

A configuration for `RESOURCE_SHARES` looks like:

```yaml
- name: gpu
  seconds: 30
```

Members of the same group run in round‑robin order, yielding after the specified number of seconds.

## Writing a module

Implement two callables and pass them to `features.F4.home_index_module.run_server`:

```python
from features.F4.home_index_module import run_server

VERSION = 1

def check(file_path, document, metadata_dir_path):
    """Return ``True`` when ``run`` should process the document."""
    version_file = metadata_dir_path / "version.json"
    if not version_file.exists():
        return True
    return version_file.read_text() != str(VERSION)

def run(file_path, document, metadata_dir_path):
    """Perform the work and return either the document or a result dict."""
    # write artifacts to ``metadata_dir_path``
    return document

if __name__ == "__main__":
    run_server(check, run)
```

`run_server` continuously works through a check queue followed by a run queue. When `check` returns ``True`` the document moves to the run queue; otherwise it is considered complete and reported to the host. Each run job writes a `log.txt` inside the file's metadata folder capturing stdout and stderr while `run` executes. The function also honours `RESOURCE_SHARES` so modules with heavy dependencies can take turns.

``check`` runs before any ``load_fn`` or ``unload_fn`` hooks, so it should be fast and avoid heavy operations. ``run`` is where intensive work happens. If a job exceeds ``TIMEOUT`` while ``run`` executes, its output is discarded and the file will be returned to the queue for processing later.

Optional `load_fn` and `unload_fn` parameters provide hooks for loading models or cleaning up resources before and after processing a share group.

Results pushed to `modules:done` may include:

```python
{
    "document": <updated file document>,
    "chunk_docs": [<chunk documents>],
    "delete_chunk_ids": [<obsolete chunk ids>]
}
```

Where chunk documents follow `docs/meilisearch_file_chunk.schema.json`.

## Helper functions

The ``home_index_module`` package exposes utilities for building chunk-based modules:

- `segments_to_chunk_docs(segments, file_id, module_name="chunk")` – convert raw segments to chunk documents with stable IDs.
- `split_chunk_docs(chunk_docs, model="intfloat/e5-small-v2", tokens_per_chunk=450, chunk_overlap=50)` – divide oversized chunks by token count using the LangChain text splitter.
- `write_chunk_docs(metadata_dir_path, chunk_docs, filename="chunks.json")` – write chunk documents to a JSON file and return its path.

These helpers originate from `features.F5.chunk_utils` and are re-exported by `home_index_module` for convenience.

## Building

The example under `features/F4/module_template` shows a minimal structure.  Build a container with:

```bash
docker build -f Dockerfile.module -t my-module:latest .
```

Run the container alongside Home Index with `QUEUE_NAME` and other variables set, then watch the metadata folder for new `log.txt` and result files.
