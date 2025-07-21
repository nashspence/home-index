"""Feature F2 package."""

from __future__ import annotations

import importlib
import types

__all__ = [
    "metadata_store",
    "path_links",
    "duplicate_finder",
    "migrations",
    "search_index",
]


def __getattr__(name: str) -> types.ModuleType:
    if name in __all__:
        module = importlib.import_module(f"{__name__}.{name}")
        globals()[name] = module
        return module
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
