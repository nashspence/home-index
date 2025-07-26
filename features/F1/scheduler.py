from __future__ import annotations

import os
from typing import Callable, Dict

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

from shared.logging_config import files_logger


def parse_cron_env(
    env_var: str = "CRON_EXPRESSION", default: str = "0 2 * * *"
) -> Dict[str, str]:
    """Return CronTrigger kwargs from the CRON_EXPRESSION environment variable."""
    cron_expression = os.getenv(env_var, default)
    parts = cron_expression.split()
    if len(parts) == 5:
        return {
            "minute": parts[0],
            "hour": parts[1],
            "day": parts[2],
            "month": parts[3],
            "day_of_week": parts[4],
        }
    if len(parts) == 6:
        return {
            "second": parts[0],
            "minute": parts[1],
            "hour": parts[2],
            "day": parts[3],
            "month": parts[4],
            "day_of_week": parts[5],
        }
    raise ValueError(
        f"Invalid cron expression in {env_var}: '{cron_expression}'. Must have 5 or 6 fields."
    )


def attach_sync_job(
    scheduler: BackgroundScheduler, debug: bool, run_fn: Callable[[], None]
) -> None:
    """Attach the periodic sync job to the scheduler."""
    try:
        trigger = (
            IntervalTrigger(seconds=60) if debug else CronTrigger(**parse_cron_env())
        )
    except ValueError:
        files_logger.error("invalid cron expression")
        raise

    scheduler.add_job(run_fn, trigger, max_instances=1)
