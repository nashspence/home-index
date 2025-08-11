# ADR – f5 Search file chunks by concept

### 2025-07-21 Initial implementation
- Module-generated text for each file is chunked and embedded using `intfloat/e5-small-v2`.
- Chunk embeddings are stored in the `file_chunks` index for semantic search.
- Queries perform vector or hybrid search to retrieve relevant text snippets.
- Implementation in `chunking.py` and `chunk_utils` manages chunk docs.
- Provides keyword-free search over file content.
