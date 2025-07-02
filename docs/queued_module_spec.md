# Queued Module Specification

Home Index modules extend the indexer with specialised processors such as caption generators, OCR engines or metadata extractors. Modules run as small services that communicate solely through Redis lists.

Each module requires these environment variables:

- `QUEUE_NAME` – unique key for the module's queue.
- `REDIS_HOST` – Redis connection string like `http://redis:6379`.
- `TIMEOUT` – seconds to allow a job to run before requeueing.
- `WORKER_ID` – unique identifier for the running instance when using resource sharing.
- `RESOURCE_SHARES` – optional YAML list of resource share groups.

Modules first drain `<QUEUE_NAME>:check`. Each entry is a JSON encoded file document following `docs/meilisearch_document.schema.json`. If `check_fn` returns `True`, the module enqueues the document on `<QUEUE_NAME>:run`; otherwise it pushes the unmodified document to `modules:done`. When pulling from either queue it records the job in `<QUEUE_NAME>:<type>:processing` and adds `{"q": queue, "d": doc_json}` to the global `timeouts` sorted set with the expiration time. After the job finishes it removes both entries and, for run jobs, pushes the result to `modules:done`.

The runtime follows Redis's [reliable queue pattern](https://github.com/redis/docs/blob/main/content/commands/lmove.md#L123-L147). Jobs move from `<QUEUE_NAME>:run` to `<QUEUE_NAME>:run:processing` with `BLMOVE` so they aren't lost if a worker crashes. Another process periodically pops expired entries from `timeouts` using `ZPOPMIN` and requeues them with `LPUSH` while removing them from the processing list atomically via a pipeline.

If `RESOURCE_SHARES` is defined, it should contain entries like:

```yaml
- name: gpu
  seconds: 30
```

Modules belonging to the same group execute in round-robin order, yielding after their allotted time.

`features.F4.home_index_module.run_server` implements this loop and writes a `log.txt` under each file's metadata folder while `check` and `run` execute. Helper functions such as `segments_to_chunk_docs` are provided for convenience.

The example module under `features/F4/module_template` demonstrates the pattern.

To build a module container:

```bash
docker build -f Dockerfile.module -t my-module:latest .
```
