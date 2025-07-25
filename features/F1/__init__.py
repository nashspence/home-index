"""Feature F1 package."""

# Re-export the scheduler module so tests can access it as ``features.F1.scheduler``.
try:
    from . import scheduler
except Exception:  # pragma: no cover - optional during tests
    scheduler = None  # type: ignore

__all__ = ["scheduler"]
