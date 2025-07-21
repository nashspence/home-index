# ADR – F3 Offline media remains searchable

### 2025-07-21 Initial implementation
- Supports an `ARCHIVE_DIRECTORY` to track files on removable media.
- Metadata retains paths even when drives are unplugged.
- Drive marker files record whether a device has been fully processed.
- Sync logic checks mount state to set online/offline flags.
- Enables searching across archived media without the drive present.
