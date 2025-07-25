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

| #     | Scenario & pre‑conditions                                                                                 | Steps (user actions → expected behaviour)                                                                                                                                                                                                                                                    |
| ----- | --------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **1** | **Initial run — existing files indexed**<br>Stack started with a valid cron and ≥ 1 file already present. | 1 Start stack → `$LOGGING_DIRECTORY/files.log` created.<br>2 A `… start file sync` line appears **during start‑up** (bootstrap); a second line appears at the **first cron tick**.<br>3 For each file, `$METADATA_DIRECTORY/by-id/<hash>/document.json` is written; file becomes searchable. ([test](tests/acceptance/s1/test_s1.py)) |
| **2** | **New file appears mid‑run**                                                                              | 1 Copy a new file into `$INDEX_DIRECTORY` between ticks.<br>2 At the **next tick** metadata and index entries for that file are created. ([test](tests/acceptance/s2/test_s2.py))                                                                                                                                                     |
| **3** | **File contents change**                                                                                  | 1 Replace bytes of an existing file (hash changes).<br>2 At next tick a **new** metadata directory (new hash) is created; old one remains untouched. ([test](tests/acceptance/s3/test_s3.py))                                                                                                                                         |
| **4** | **Regular cadence honoured**                                                                              | 1 Let stack run several ticks.<br>2 Interval between successive `start file sync` lines matches the cron ± 1 s and **never faster**. ([test](tests/acceptance/s4/test_s4.py))                                                                                                                                                         |
| **5** | **Long‑running sync never overlaps**                                                                      | 1 Choose a cron shorter than the scan duration.<br>2 A second `start file sync` line never appears until the previous run logs `… completed file sync`. ([test](tests/acceptance/s5/test_s5.py))                                                                                                                                      |
| **6** | **Change schedule**                                                                                       | 1 Stop containers.<br>2 Edit `CRON_EXPRESSION` to any valid value.<br>3 Restart → new cadence is observed. ([test](tests/acceptance/s6/test_s6.py))                                                                                                                                                                                   |
| **7** | **Restart with same schedule**                                                                            | 1 After any successful run, stop containers.<br>2 Start them again with the **identical** cron expression → service reuses the existing `$LOGGING_DIRECTORY`, appends to `files.log`, and performs the usual bootstrap + scheduled ticks. ([test](tests/acceptance/s7/test_s7.py))                                                    |
| **8** | **Invalid cron blocks start‑up**                                                                          | 1 Set `CRON_EXPRESSION` to `bad cron`.<br>2 Start stack → Home‑Index exits non‑zero, logs “invalid cron expression”, container stays stopped. ([test](tests/acceptance/s8/test_s8.py))                                                                                                                                                |

All scenarios must pass on Linux, macOS, and Windows (WSL) without altering this spec—only the concrete cron strings, file names, and timestamps vary by project.

---

**End of specification**
