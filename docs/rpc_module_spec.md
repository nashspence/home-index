# RPC Module Specification

Home Index modules extend the indexer with specialised processors such as
caption generators, OCR engines or metadata extractors. A module is a small
service that speaks XML‑RPC. Home Index calls these services for every file so
they can add fields or create chunk documents. Modules may run locally or on a
different machine as long as the endpoint is reachable.

The directory `features/F4/module_template/` contains a minimal reference
implementation. Each module is packaged as a container built from
`Dockerfile.module` and started with
`features.F4.home_index_module.run_server`. The helper configures logging and
directories then exposes the RPC functions described below.

## hello()
Returns a JSON object describing the module. Example:
```json
{
  "name": "example",
  "version": 1,
  "target": "abcdef123",
  "filterable_attributes": ["field"],
  "sortable_attributes": []
}
```
- `name` – unique identifier for the module.
- `version` – increment when the module behaviour changes.
- `target` – commit SHA or tag of Home Index the module expects.
- `filterable_attributes` – optional list of additional fields that should be
  declared filterable in Meilisearch.
- `sortable_attributes` – optional list of additional fields that should be
  sortable.

## check(docs)
`docs` is a JSON array of file documents following
`docs/meilisearch_document.schema.json`.
The call returns a JSON array containing the IDs of the documents that should be
processed by `run`.
When using `run_server`, the provided `check_fn` is called for each document with
`(file_path, document, metadata_dir_path)` and should return `True` to process
that document. Modules typically record their own version information under
`metadata_dir_path` so `check` can skip documents that were already processed by
the current version.

## run(document)
`document` is a JSON representation of a file document. The function performs
work for the file and returns either the updated document or an object of the
form:
```json
{
  "document": { ...updated document... },
  "chunk_docs": [ { ...chunk document... } ],
  "delete_chunk_ids": ["chunk-id"]
}
```
`chunk_docs` use the schema defined in `docs/meilisearch_file_chunk.schema.json`.
`delete_chunk_ids` lists any chunk documents that should be removed.

## load()
Optional. Called once before a batch of documents is processed.

## unload()
Optional. Called once after the batch is processed.

## Environment variables

`run_server` reads a few variables to configure paths and logging:

- `HOST` – network interface to bind (default `0.0.0.0`).
- `PORT` – listening port (default `9000`).
- `FILES_DIRECTORY` – location of the shared files (default `/files`).
- `METADATA_DIRECTORY` – root directory for module metadata (default `/files/metadata`).
- `BY_ID_DIRECTORY` – overrides where per-file metadata is stored. Defaults to
  `<METADATA_DIRECTORY>/by-id`.
- `LOGGING_LEVEL` – log level for console and file logs.
- `DEBUG` / `WAIT_FOR_DEBUGPY_CLIENT` – enable debugpy and optionally wait for a
  debugger before starting.

## Helper functions

`features.F4.home_index_module` exposes utilities for common module tasks:

- `run_server(name, hello_fn, check_fn, run_fn, load_fn=None, unload_fn=None)` –
  starts the XML‑RPC server and writes a `log.txt` under each file's metadata
  folder while `check` and `run` execute.
- `segments_to_chunk_docs(segments, file_id, module_name="chunk")` – convert raw
  text segments to chunk documents with unique IDs.
- `split_chunk_docs(chunk_docs, model="intfloat/e5-small-v2", tokens_per_chunk=450, chunk_overlap=50)` – split long chunks by token count using
  LangChain. Raises an error if the optional dependency is missing.
- `write_chunk_docs(metadata_dir_path, chunk_docs, filename="chunks.json")` –
  write chunk metadata to disk for inspection or later processing.

The example module under `features/F4/module_template` demonstrates these
helpers in context.

`segments_to_chunk_docs` converts raw text segments into Meilisearch chunk
documents. Use it when your module produces longer passages that should be
searchable through the concept search feature. `split_chunk_docs` further breaks
large chunks by token count so they fit the search index limits. Both helpers
are thin wrappers around LangChain and require the optional dependencies
included in `Dockerfile.module`.

`write_chunk_docs` simply dumps a list of chunk metadata to disk. This is handy
when debugging or when another process wants to review the generated data before
it is indexed.

## Packaging and release

The easiest way to ship a module is to build a container based on
`Dockerfile.module`:

```bash
docker build -f Dockerfile.module -t my-module:latest \
  --build-arg COMMIT_SHA=$(git rev-parse HEAD) .
```

The `COMMIT_SHA` build argument pins the Home Index commit the module was built
against. The same value must be returned from `hello()["target"]` so Home Index
can verify compatibility. After building, publish the image to a container
registry and run it with an XML‑RPC endpoint exposed (port `9000` by default).

Home Index discovers modules through the `MODULES` environment variable, which
is a comma separated list of `http://host:port` entries. Modules can therefore
live on the same host or anywhere reachable over the network.
