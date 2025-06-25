from __future__ import annotations

from typing import MutableMapping, Any

from . import metadata_store

# List of migration functions to upgrade stored metadata documents.
MIGRATIONS = [metadata_store._add_paths_list]

# Schema version corresponding to the last migration in ``MIGRATIONS``.
CURRENT_VERSION = len(MIGRATIONS)


def migrate_doc(doc: MutableMapping[str, Any]) -> bool:
    """Apply pending migrations to ``doc`` in-place."""
    version = doc.get("version", 0)
    migrated = False
    while version < CURRENT_VERSION:
        MIGRATIONS[version](doc)
        migrated = True
        version = doc.get("version", version + 1)
    return migrated
