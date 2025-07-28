# F1 Scheduled file‑sync

## 1 Why schedule a sync?

A scheduled scan keeps Home‑Index responsive: the service sleeps between ticks, then crawls **all files under `$INDEX_DIRECTORY`** (defaults to `/files`), writing metadata into `$METADATA_DIRECTORY` and logs into `$LOGGING_DIRECTORY`. Users never press a “re‑index” button; new or changed files appear automatically after the next tick.

*Note:* on start‑up the app performs **one immediate bootstrap sync** before the scheduler begins its cadence.

---

## 2 Configuring the schedule

Declare a single variable:

```yaml
CRON_EXPRESSION: "* * * * *"          # every minute – any valid cron is OK
```

* **Default when unset:** `0 2 * * *` (02:00 daily, container time).
* Accepts **5‑field** (`m h dom mon dow`) or **6‑field** (`s m h dom mon dow`) syntax. Include the seconds column for sub‑minute schedules (`*/10 * * * * *` = every 10 s).
* The schedule is evaluated in the container’s local zone (UTC by default). Change with `TZ`, e.g. `TZ=America/Los_Angeles`.

---

## 3 Minimal `docker-compose.yml`

```yaml
services:
  home-index:
    image: ghcr.io/nashspence/home-index:latest
    environment:
      - CRON_EXPRESSION=* * * * *           # edit to taste
    volumes:
      - ./input:$INDEX_DIRECTORY:ro         # project files (read‑only)
      - ./output:$LOGGING_DIRECTORY         # logs
    depends_on: [meilisearch]

  meilisearch:
    image: getmeili/meilisearch:latest
    environment: [MEILI_NO_ANALYTICS=true]
    volumes: [./output/meili:/meili_data]
```

---

## 4 Acceptance criteria (platform‑agnostic)

```gherkin
@f1 @s1
Scenario: Initial run — existing files indexed
  Given the stack started with a valid cron expression
    And at least one file exists in $INDEX_DIRECTORY
  When the stack boots
  Then $LOGGING_DIRECTORY/files.log is created
    And a "start file sync" line appears during start-up
    And another "start file sync" line appears at the first cron tick
    And for each file $METADATA_DIRECTORY/by-id/<hash>/document.json is written
    And each file becomes searchable
```
([test](tests/acceptance/s1/test_s1.py))

```gherkin
@f1 @s2
Scenario: New file appears mid-run
  Given the stack is running
  When a new file is copied into $INDEX_DIRECTORY between ticks
  Then at the next tick metadata and index entries for that file are created
```
([test](tests/acceptance/s2/test_s2.py))

```gherkin
@f1 @s3
Scenario: File contents change
  Given an existing file's bytes are replaced so its hash changes
  When the next tick runs
  Then a new metadata directory is created for the new hash
    And the old directory remains untouched
```
([test](tests/acceptance/s3/test_s3.py))

```gherkin
@f1 @s4
Scenario: Regular cadence honoured
  When the stack runs for several ticks
  Then the interval between successive "start file sync" lines matches the cron ± 1 s
    And never faster
```
([test](tests/acceptance/s4/test_s4.py))

```gherkin
@f1 @s5
Scenario: Long-running sync never overlaps
  Given the cron schedule is shorter than the scan duration
  When the stack runs
  Then a second "start file sync" line never appears until the previous run logs "… completed file sync"
```
([test](tests/acceptance/s5/test_s5.py))

```gherkin
@f1 @s6
Scenario: Change schedule
  Given the stack is stopped
  When $CRON_EXPRESSION is edited to any valid value
    And the stack restarts
  Then the new cadence is observed
```
([test](tests/acceptance/s6/test_s6.py))

```gherkin
@f1 @s7
Scenario: Restart with same schedule
  Given a previous run succeeded
    And the containers are stopped
  When they start again with the identical cron expression
  Then the service reuses the existing $LOGGING_DIRECTORY
    And files.log continues to append
    And the usual bootstrap and scheduled ticks occur
```
([test](tests/acceptance/s7/test_s7.py))

```gherkin
@f1 @s8
Scenario: Invalid cron blocks start-up
  Given CRON_EXPRESSION is set to "bad cron"
  When the stack starts
  Then Home-Index exits with a non-zero code
    And logs "invalid cron expression"
    And the container stays stopped
```
([test](tests/acceptance/s8/test_s8.py))

All scenarios must pass in the provided container environment. Only the concrete cron strings, file names, and timestamps may vary by project.

---

**End of specification**
