# ADR – f1 Scheduled file-sync

### 2025-07-21 Initial implementation
- Uses APScheduler to schedule syncs based on `CRON_EXPRESSION`.
- Performs one bootstrap sync on start then runs on the configured schedule.
- `parse_cron_env` supports 5- or 6-field cron expressions.
- Debug mode switches to an interval trigger for rapid testing.
- Chosen for simple configuration and reliable timing.

### 2025-07-22 Scheduler logging
- Log an explicit "invalid cron expression" error when `CRON_EXPRESSION` cannot
  be parsed. Tightens acceptance tests around startup failures.
