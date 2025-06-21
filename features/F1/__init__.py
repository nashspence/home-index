"""Feature F1 package."""

# Re-export the scheduler module so tests can access it as ``features.F1.scheduler``.
from . import scheduler

__all__ = ["scheduler"]
