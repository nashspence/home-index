from __future__ import annotations

import os
from typing import Callable, Dict

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.triggers.cron import CronTrigger
from shared.logging_config import files_logger


def parse_cron_env(
    env_var: str = "CRON_EXPRESSION", default: str = "0 2 * * *"
) -> Dict[str, str]:
    """Return CronTrigger kwargs from the CRON_EXPRESSION environment variable."""
    cron_expression = os.getenv(env_var, default)
    files_logger.debug("parse_cron_env: %s=%s", env_var, cron_expression)
    parts = cron_expression.split()
    if len(parts) == 5:
        kwargs = {
            "minute": parts[0],
            "hour": parts[1],
            "day": parts[2],
            "month": parts[3],
            "day_of_week": parts[4],
        }
        files_logger.debug("parsed 5 field cron -> %s", kwargs)
        return kwargs
    if len(parts) == 6:
        kwargs = {
            "second": parts[0],
            "minute": parts[1],
            "hour": parts[2],
            "day": parts[3],
            "month": parts[4],
            "day_of_week": parts[5],
        }
        files_logger.debug("parsed 6 field cron -> %s", kwargs)
        return kwargs
    raise ValueError(
        f"Invalid cron expression in {env_var}: '{cron_expression}'. Must have 5 or 6 fields."
    )


def attach_sync_job(
    scheduler: BackgroundScheduler, debug: bool, run_fn: Callable[[], None]
) -> None:
    """Attach the periodic sync job to the scheduler."""
    files_logger.debug("attach_sync_job: debug=%s", debug)
    trigger = IntervalTrigger(seconds=60) if debug else CronTrigger(**parse_cron_env())
    files_logger.debug("using trigger %s", trigger)
    scheduler.add_job(run_fn, trigger, max_instances=1)
    files_logger.debug("sync job attached")
