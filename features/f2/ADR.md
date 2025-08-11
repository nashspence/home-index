# ADR – f2 Search for unique files by metadata

### 2025-07-21 Initial implementation
- Files are identified by an xxhash64 hash computed from their contents.
- Metadata stored under `metadata/by-id/<hash>/document.json` with symlinks from `by-path`.
- Duplicate paths point to the same canonical document.
- Search index built via Meilisearch to enable metadata queries.
- Approach chosen to deduplicate data and speed up searches.
