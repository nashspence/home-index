# RPC Module Specification

Home Index modules are independent services that expose an XML‑RPC interface. The
server can be started with `features.F4.home_index_module.run_server` which takes functions
implementing the calls described below.

## hello()
Returns a JSON object describing the module. Example:
```json
{
  "name": "example",
  "version": 1,
  "filterable_attributes": ["field"],
  "sortable_attributes": []
}
```
- `name` – unique identifier for the module.
- `version` – increment when the module behaviour changes.
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
that document.

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
