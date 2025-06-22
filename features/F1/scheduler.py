from __future__ import annotations

import os
from typing import Callable

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.triggers.cron import CronTrigger


def parse_cron_env(
    env_var: str = "CRON_EXPRESSION", default: str = "0 3 * * *"
) -> CronTrigger:
    """Return a ``CronTrigger`` built from the given environment variable."""
    cron_expression = os.getenv(env_var, default)
    try:
        return CronTrigger.from_crontab(cron_expression)
    except ValueError as exc:  # pragma: no cover - defensive
        raise ValueError(
            f"Invalid cron expression in {env_var}: '{cron_expression}'."
        ) from exc


def attach_sync_job(
    scheduler: BackgroundScheduler, debug: bool, run_fn: Callable[[], None]
) -> None:
    """Attach the periodic sync job to the scheduler."""
    trigger = IntervalTrigger(seconds=60) if debug else parse_cron_env()
    scheduler.add_job(run_fn, trigger, max_instances=1)
