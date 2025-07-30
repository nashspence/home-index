# F1 Scheduled file‑sync

## 1 Why schedule a sync?

A scheduled scan keeps Home‑Index responsive: the service sleeps between ticks, then crawls **all files under `$INDEX_DIRECTORY`** (defaults to `/files`), writing metadata into `$METADATA_DIRECTORY` and logs into `$LOGGING_DIRECTORY`. Users never press a “re‑index” button; new or changed files appear automatically after the next tick.

*Note:* on start‑up the app performs **one immediate bootstrap sync** before the scheduler begins its cadence.

---

## 2 Configuring the schedule

Declare a single variable:

```yaml
CRON_EXPRESSION: "* * * * *" # every minute – any valid cron is OK
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
      - CRON_EXPRESSION=* * * * * # edit to taste
    volumes:
      - ./input:$INDEX_DIRECTORY:ro # project files (read‑only)
      - ./output:$LOGGING_DIRECTORY # logs
    depends_on: [meilisearch]

  meilisearch:
    image: getmeili/meilisearch:latest
    environment: [MEILI_NO_ANALYTICS=true]
    volumes: [./output/meili:/meili_data]
```

---

## 4 Acceptance criteria (platform-agnostic)

```gherkin
@f1
Feature: Scheduled file sync

  Rule: Bootstrap and normal operation
    @s1
    # [test](tests/acceptance/s1/test_s1.py)
    Scenario: Index existing files on first run
      Given a file exists in the index directory
      When containers start
        And home_index container logs show, in order:
          | [INFO] completed file sync |
      Then $LOGGING_DIRECTORY exists
        And files.log is created there
        And $METADATA_DIRECTORY exists
        And for each file in the index directory a directory named by its hash is in it
        And document.json is written in each of those directories
        And each file is searchable

    @s2
    # [test](tests/acceptance/s2/test_s2.py)
    Scenario: Index file added between sync ticks
      Given a file exists in the index directory
      When containers start
        And home_index container logs show, in order:
          | [INFO] completed file sync |
        And a new unique file is copied into $INDEX_DIRECTORY
        And home_index container logs show, in order:
          | [INFO] completed file sync |
      Then $METADATA_DIRECTORY exists
        And a directory named the new file's hash is in it
        And document.json is written in that directory
        And the new file is searchable


    @s3
    # [test](tests/acceptance/s3/test_s3.py)
  Scenario: Track modified file by new hash
    Given the stack started
      And a file exists in $INDEX_DIRECTORY with no copies
    When the logs contain, in order:
        | container  | line_regex              |
        | home_index | ^\[INFO\] start file sync$ |
        | home_index | ^\[INFO\] completed file sync$ |
    Then an existing file's bytes are replaced so its hash changes
      And the logs contain, in order:
        | container  | line_regex              |
        | home_index | ^\[INFO\] start file sync$ |
        | home_index | ^\[INFO\] commit changes to meilisearch$ |
        | home_index | ^\[INFO\] completed file sync$ |
      And a new metadata directory is created for the new hash
      And the old directory is removed

    @s4
    # [test](tests/acceptance/s4/test_s4.py)
  Scenario: Honour configured cadence
    When the stack runs for several ticks
    Then the logs contain, in order:
        | container  | line_regex          |
        | home_index | ^\[INFO\] start file sync$ |
        | home_index | ^\[INFO\] start file sync$ |
        | home_index | ^\[INFO\] start file sync$ |
        And the interval between successive "start file sync" lines matches the cron +- 3 s
        And never faster

    @s5
    # [test](tests/acceptance/s5/test_s5.py)
  Scenario: Do not overlap sync runs
    Given the cron schedule is shorter than the scan duration
    When the stack runs
    Then the logs contain, in order:
        | container  | line_regex            |
        | home_index | ^\[INFO\] start file sync$ |
        | home_index | ^\[INFO\] completed file sync$ |
        | home_index | ^\[INFO\] start file sync$ |
      And a second "start file sync" line never appears until the previous run logs "... completed file sync"

  Rule: Schedule management
    @s6
    # [test](tests/acceptance/s6/test_s6.py)
  Scenario: Apply new schedule after restart
    Given the stack is stopped
      And $CRON_EXPRESSION is edited to any valid value
    When the stack restarts
    Then the logs contain, in order:
        | container  | line_regex          |
        | home_index | ^\[INFO\] start file sync$ |
        | home_index | ^\[INFO\] start file sync$ |
        | home_index | ^\[INFO\] start file sync$ |
        And the interval between successive "start file sync" lines matches the new cron +- 3 s

    @s7
    # [test](tests/acceptance/s7/test_s7.py)
  Scenario: Reuse logs on restart
    Given the stack has booted
    When the logs contain, in order:
        | container  | line_regex          |
        | home_index | ^\[INFO\] start file sync$ |
        | home_index | ^\[INFO\] start file sync$ |
    Then the containers are stopped
      And they start again with the identical cron expression
      And the service reuses the existing $LOGGING_DIRECTORY
      And the logs contain, in order:
        | container  | line_regex          |
        | home_index | ^\[INFO\] start file sync$ |
        And files.log continues to append
        And the usual bootstrap and scheduled ticks occur

    @s8
    # [test](tests/acceptance/s8/test_s8.py)
  Scenario: Exit on invalid cron
    Given CRON_EXPRESSION is set to "bad cron"
    When the stack starts
    Then Home-Index exits with a non-zero code
      And the logs contain, in order:
        | container  | line_regex            |
        | home_index | ^\[ERROR\] invalid cron expression$ |
      And the container stays stopped
```

All scenarios must pass in the provided container environment. Only the concrete cron strings, file names, and timestamps may vary by project.

---

**End of specification**
