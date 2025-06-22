# F1. “I want scheduled file-sync”

## Value

Scheduled sync keeps your server responsive while new files are indexed at predictable times. Fresh metadata appears automatically—no manual triggers required.

---

## Usage

Provide a [cron expression](https://crontab.guru/) in the CRON_EXPRESSION environment variable to the container at startup using a docker-compose.yml file or similar.

---

## Minimal `docker-compose.yml`

```yaml
services:
  home-index:
    image: ghcr.io/nashspence/home-index:latest
    environment:
      - CRON_EXPRESSION=* * * * *        # every minute; edit to taste
      - METADATA_DIRECTORY=/home-index/metadata
    volumes:
      - ./input:/files:ro                # place source files here (read-only)
      - ./output:/home-index             # logs, metadata, appear here
    depends_on:
      - meilisearch

  meilisearch:
    image: getmeili/meilisearch:latest
    volumes:
      - ./output/meili:/meili_data       # search index persists on host
```

---

## User Testing

```bash
# 0. (Optional) change cadence:
#    edit CRON_EXPRESSION in docker-compose.yml, e.g.
#    - CRON_EXPRESSION=*/5 * * * *      # every five minutes

mkdir -p input output                    # create bind-mount folders

# 1. Ensure there is at least ONE file to index
echo "hello world" > input/hello.txt     # example seed file

# 2. Launch the stack
docker compose up -d                     # pull images & start services

# 3. Watch it run
tail -f output/files.log                 # see a new “start file sync” line each tick
```

**What you’ll see after the first tick**

```
output/
├ files.log
├ metadata/
│   └ by-id/
│       ├ <xxhash-of-hello.txt>/
│       │   ├ document.json
│       │   └ …                       ← any side-car artifacts
│       └ …                           ← one folder per file hash in ./input
└ meili/
    └ …                               ← search index files
```

Change the cron schedule any time by editing the compose file and running:

```bash
docker compose up -d --force-recreate
```

The new cadence takes effect immediately; the rhythm in **`output/files.log`** updates accordingly.

---

## Input ↔ Output

| **Your single action**                                                                                                                                                                                                                                                                         | **What you will literally see**                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                    |
| ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **1. Edit `CRON_EXPRESSION` in `docker-compose.yml` and immediately run**<br>`docker compose up -d` <br>*(or `docker compose up -d --force-recreate` if the stack is already running)* | On the **first tick** after the containers come up:<br>1. `./output/` is recreated from scratch.<br>2. A line like `YYYY-MM-DD HH:MM:SS,mmm start file sync` is appended to **`output/files.log`** exactly at the cadence implied by the cron string you set.<br>3. For every file in `./input/`, a directory named by that file’s **xxhash** appears under **`output/metadata/by-id/<xxhash>/…`** containing `document.json` and any side-car artifacts.<br>4. The MeiliSearch index is seeded or updated in **`output/meili/`**. |
| **2. Add or modify a file in `./input/` while the containers are running**                                                                                                                                                                                                                     | On the **next** cron tick:<br>• A new (or updated) xxhash-named directory appears under `metadata/by-id/`, and<br>• A fresh “start file sync” line is appended to `files.log`.                                                                                                                                                                                                                                                                                                                                                     |
| **3. Run `docker compose stop`**                                                                                                                                                                                                                                                               | The current sync finishes, a final timestamped log entry is written, and containers halt; everything in **`./output/`** remains intact for inspection or backup.                                                                                                                                                                                                                                                                                                                                                                   |
                                          
---

## Acceptance

1. **Cadence fidelity** Time between any two consecutive “start file sync” lines is **never shorter** than the cron interval you configured (verified ±1 s).
2. **Clean slate per start** `./output/` is wiped and rebuilt on every container start, so logs & metadata always correspond to *that* run.
3. **Proof of successful indexing** With at least one file in `./input/`, the first tick creates a directory under `./output/metadata/by-id/`, and MeiliSearch data persists in `./output/meili/`.
