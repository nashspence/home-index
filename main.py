import asyncio
import os

from features.F1 import sync as f1_sync
from apscheduler.triggers.cron import CronTrigger
from features.F2 import migrations, duplicate_finder
from features.F3 import archive
from features.F4 import modules as modules_f4
from features.F6 import server as f6_server
from shared.logging_config import files_logger, setup_logging

DEBUG = str(os.environ.get("DEBUG", "False")) == "True"
COMMIT_SHA = os.environ.get("COMMIT_SHA", "unknown")

# re-export helpers used by legacy tests
parse_cron_env = f1_sync.parse_cron_env
index_metadata = f1_sync.index_metadata
index_files = f1_sync.index_files
update_metadata = f1_sync.update_metadata
get_mime_type = f1_sync.get_mime_type
archive = archive
CURRENT_VERSION = migrations.CURRENT_VERSION
duplicate_finder = duplicate_finder


async def main() -> None:
    setup_logging()
    files_logger.info("running commit %s", COMMIT_SHA)
    # Validate cron expression early so startup fails fast on bad config.
    if not DEBUG:
        try:
            CronTrigger(**parse_cron_env())
        except ValueError:
            files_logger.error("invalid cron expression")
            raise
    await f1_sync.init_meili_and_sync()
    if modules_f4.is_modules_changed:
        modules_f4.modules_logger.info("*** perform sync on MODULES changed")
        await f1_sync.init_meili_and_sync()
        modules_f4.save_modules_state()
    await asyncio.gather(
        f1_sync.schedule_and_run(f6_server.serve_api, debug=DEBUG),
        modules_f4.service_module_queues(),
    )


if __name__ == "__main__":
    asyncio.run(main())
