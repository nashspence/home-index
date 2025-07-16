# Queued Module Specification

Home Index modules extend the indexer with specialised processors such as caption generators, OCR engines or metadata extractors.  Modules run as small services that communicate solely through Redis lists and write their results under each file's metadata directory.

## Configuring Home Index

Set a single environment variable on the **home-index** service listing the queue names to process:

```yaml
QUEUES: |
  - example-module
  - another-module
```

Each module container advertises its queue via the `QUEUE_NAME` variable and must appear in this list.

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

Modules should return the processed document and may also return a `content`
value containing raw text or a list of segment objects. When present this
content is written to `content.json` under the module's metadata directory.

Each segment object must provide a `text` key and may include:

- `header` – mapping of metadata that will be formatted as a prefix like
  `[speaker: A]`.
- `time_offset`/`time_length` – optional floating point offsets suitable for
  audio or video timestamps.
- `start_time` – epoch seconds when the segment begins. When omitted,
  Home Index defaults to the file's `mtime` plus `time_offset`.
- `char_offset`/`char_length` – integer character offsets. When omitted,
  Home Index calculates them based on the final chunk text.

Home Index splits segments into chunk documents and stores them in
`chunks.json` under `metadata/by-id/<file-id>/<QUEUE_NAME>/`. Chunks can be
rebuilt later from the stored `content.json` whenever chunk settings change.

## Building

The example under `features/F4/module_template` shows a minimal structure.  Build a container with:

```bash
docker build -f Dockerfile.module -t my-module:latest .
```

Run the container alongside Home Index with `QUEUE_NAME` and other variables set, then watch the metadata folder for new `log.txt` and result files.
