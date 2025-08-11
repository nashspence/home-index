# ADR – f6 Remote file operations via API

### 2025-07-21 Initial implementation
- Uses FastAPI and AsgiWebDAV to expose HTTP endpoints and a WebDAV share.
- Supports uploading, renaming, moving and deleting files remotely.
- `server.py` runs the API with uvicorn.
- After each operation, metadata is refreshed so search results stay current.
- Allows clients to modify files without direct filesystem access.
